"""5-step adversarial debate engine for conflicting loyalty-program claims.

When two sources disagree on the same extracted field, two advocate LLM agents
argue for their claim using only the structured claim metadata (recency,
authority, corroboration, volatility), optionally rebut each other, and a
judge produces a deterministic JSON verdict. The engine is program-agnostic:
all program facts come from the conflict dict supplied by the caller.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from providers import provider_for_stage


DEFAULT_DEBATE_MODEL = "llama3-70b-8192"
SIMILARITY_THRESHOLD = 0.80

# Advocate temperature 0.3: enough variation to surface different argument
# angles between advocates, but not creative enough to drift from metadata.
ADVOCATE_TEMPERATURE = 0.3
ADVOCATE_MAX_TOKENS = 200
REBUTTAL_MAX_TOKENS = 150

# Judge temperature 0.1: the verdict must be deterministic and reproducible;
# the judge weighs evidence, it does not generate ideas.
JUDGE_TEMPERATURE = 0.1
JUDGE_MAX_TOKENS = 250

# Groq free-tier rate limits crash on bursts; cap in-flight calls at 3 so
# concurrent debates across multiple conflicts queue instead of failing.
_GROQ_SEMAPHORE = asyncio.Semaphore(3)
_GROQ_CLIENT = None

NO_REBUTTAL_NOTE = "No rebuttal — arguments not sufficiently differentiated."

VOLATILITY_WEIGHTS = {
    "HIGH": {"recency": 0.50, "authority": 0.25, "corroboration": 0.25},
    "LOW": {"recency": 0.20, "authority": 0.50, "corroboration": 0.30},
}

AUTHORITY_RANKING = "official > major_publication > news > aggregator > forum"

FLAG_FALLBACK_REASONING = "Judge output unparseable — manual review needed"

CLAIM_TEMPLATE = (
    "value={value} | source_url={source_url} | date={date} | "
    "authority={authority} | corroboration={corroboration} independent sources | "
    "confidence={confidence}"
)

ADVOCATE_PROMPT_TEMPLATE = """You are Advocate {advocate}. Build the strongest case that CLAIM {advocate} is the correct value for the disputed loyalty program field below. You cannot see the opposing advocate's argument.

FIELD: {field_name}
VOLATILITY: {volatility}
CONFIDENCE WEIGHTS for {volatility} volatility: recency {recency_weight} | authority {authority_weight} | corroboration {corroboration_weight}
AUTHORITY TIERS (strongest first): {authority_ranking}

CLAIM A: {claim_a}
CLAIM B: {claim_b}

RULES:
- Argue using ONLY recency, authority, corroboration, and the volatility context above.
- Do NOT invent facts about either source.
- Do NOT claim the opposing sources are related, copies, or derivative.
- Do NOT reference any knowledge beyond the metadata above.
- Be specific: cite the metadata numbers and the volatility weights. Vague appeals like "official sources are always better" are weak.

Write the argument for CLAIM {advocate} in at most 120 words."""

REBUTTAL_PROMPT_TEMPLATE = """You are Advocate {advocate}. You previously argued for CLAIM {advocate}. You can now see the opposing advocate's original argument.

OPPOSING ARGUMENT (for CLAIM {opponent}):
{opposing_argument}

FIELD: {field_name}
VOLATILITY: {volatility}
CONFIDENCE WEIGHTS for {volatility} volatility: recency {recency_weight} | authority {authority_weight} | corroboration {corroboration_weight}
AUTHORITY TIERS (strongest first): {authority_ranking}

CLAIM A: {claim_a}
CLAIM B: {claim_b}

TASK: Identify the SINGLE weakest point in the opposing argument and challenge it using only the metadata dimensions above.

Permitted rebuttal angles:
{permitted_angles}

RULES:
- Challenge exactly one weak point; do not list several.
- Do NOT simply repeat your original argument.
- Do NOT introduce any fact that is not in the metadata above (for example, never claim the opposing sources copied each other — you were not given that information).

Write the rebuttal in at most 90 words."""

REBUTTAL_ANGLES_A = """- The opponent overweights recency for a LOW volatility field.
- The opponent's corroboration comes from lower authority tier sources.
- The opponent's date advantage is within normal site update cycles.
- The volatility weights do not support the opponent's conclusion."""

REBUTTAL_ANGLES_B = """- The opponent overweights authority for a HIGH volatility field.
- The opponent's single source is outweighed by the higher corroboration count.
- The opponent's official authority does not compensate for the recency gap.
- The volatility weights do not support the opponent's authority-first conclusion."""

JUDGE_PROMPT_TEMPLATE = """You are the Judge in an adversarial debate about a disputed loyalty program field. Decide which claim is correct using only the metadata and the debate transcript below.

FIELD: {field_name}
VOLATILITY: {volatility}
CONFIDENCE WEIGHTS for {volatility} volatility: recency {recency_weight} | authority {authority_weight} | corroboration {corroboration_weight}
AUTHORITY TIERS (strongest first): {authority_ranking}

CLAIM A: {claim_a}
CLAIM B: {claim_b}

ARGUMENT A:
{argument_a}

ARGUMENT B:
{argument_b}

REBUTTAL A:
{rebuttal_a}

REBUTTAL B:
{rebuttal_b}

Evaluate in this exact order:
1. Apply the volatility weights — which signal dominates for this field?
2. Evaluate the original arguments — which made the stronger evidence case?
3. Evaluate the rebuttals — specific and grounded beats vague and repetitive. A rebuttal that introduces facts not present in the claim metadata is hallucinated and must be ignored. A rebuttal that precisely targets the opposing metadata weakness is strong and carries high weight.
4. Combine all signals into a verdict.
5. If genuinely unresolvable after all steps, return FLAG.

Output ONLY valid JSON, no preamble, no markdown fences:
{{
    "winner": "A" or "B" or "FLAG",
    "winning_value": "<chosen value or null if FLAG>",
    "deciding_factor": "recency" or "authority" or "corroboration" or "rebuttal_quality" or "unresolvable",
    "reasoning": "<one sentence naming the specific deciding factor>",
    "rebuttal_assessment": {{
        "A_rebuttal": "strong" or "weak" or "hallucinated",
        "B_rebuttal": "strong" or "weak" or "hallucinated"
    }},
    "confidence_adjustment": <float between -0.10 and +0.10>
}}"""


def _groq_client():
    global _GROQ_CLIENT
    if _GROQ_CLIENT is None:
        from groq import AsyncGroq

        api_key = provider_for_stage("debate").api_key
        if not api_key:
            raise RuntimeError("Debate engine is not configured. Set DEBATE_API_KEY or GROQ_API_KEY.")
        _GROQ_CLIENT = AsyncGroq(api_key=api_key)
    return _GROQ_CLIENT


def _debate_model() -> str:
    return provider_for_stage("debate").resolved_model or DEFAULT_DEBATE_MODEL


async def call_groq(prompt: str, temperature: float, max_tokens: int) -> str:
    """Single Groq chat completion; semaphore-gated, no retries (caller handles)."""

    async with _GROQ_SEMAPHORE:
        response = await _groq_client().chat.completions.create(
            model=_debate_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return (response.choices[0].message.content or "").strip()


def arguments_are_differentiated(argument_a: str, argument_b: str) -> bool:
    """Gate for the rebuttal rounds (Steps 3-4).

    If both advocates made essentially the same argument, rebuttals only
    restate it and waste tokens, so we measure TF-IDF cosine similarity and
    run rebuttals only when the arguments are genuinely different (< 0.80).
    """

    if not argument_a.strip() or not argument_b.strip():
        return False
    try:
        matrix = TfidfVectorizer().fit_transform([argument_a, argument_b])
    except ValueError:
        return False
    similarity = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    return similarity < SIMILARITY_THRESHOLD


def parse_judge_output(raw: str) -> dict[str, Any]:
    """Parse the judge's JSON verdict, tolerating markdown fences."""

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {
            "winner": "FLAG",
            "winning_value": None,
            "deciding_factor": "unresolvable",
            "reasoning": FLAG_FALLBACK_REASONING,
            "rebuttal_assessment": {"A_rebuttal": "weak", "B_rebuttal": "weak"},
            "confidence_adjustment": 0.0,
        }


async def run_debate(conflict: dict[str, Any], use_rebuttal: bool = True) -> dict[str, Any]:
    """Run the 5-step adversarial debate for one field conflict.

    Step 1: Advocate A argues for claim_a in isolation (metadata only).
    Step 2: Advocate B argues for claim_b in isolation (metadata only).
    Gate:   TF-IDF cosine similarity between the two arguments; rebuttals run
            only when the arguments are differentiated (similarity < 0.80).
    Step 3: Rebuttal A — A sees B's argument and challenges its single
            weakest point (conditional on the gate and use_rebuttal).
    Step 4: Rebuttal B — mirror of Step 3 (same condition).
    Step 5: Judge sees all four outputs and returns a deterministic JSON
            verdict: winner A/B, or FLAG when genuinely unresolvable.

    Returns the verdict plus the full transcript and a final confidence
    clamped to [0.0, 1.0].
    """

    field_name = str(conflict["field_name"])
    claim_a = conflict["claim_a"]
    claim_b = conflict["claim_b"]

    # Steps 1 and 2 are isolated from each other, so they can run concurrently.
    argument_a, argument_b = await asyncio.gather(
        call_groq(_advocate_prompt("A", conflict), ADVOCATE_TEMPERATURE, ADVOCATE_MAX_TOKENS),
        call_groq(_advocate_prompt("B", conflict), ADVOCATE_TEMPERATURE, ADVOCATE_MAX_TOKENS),
    )

    rebuttal_a = ""
    rebuttal_b = ""
    rebuttals_ran = use_rebuttal and arguments_are_differentiated(argument_a, argument_b)
    if rebuttals_ran:
        rebuttal_a, rebuttal_b = await asyncio.gather(
            call_groq(_rebuttal_prompt("A", conflict, argument_b), ADVOCATE_TEMPERATURE, REBUTTAL_MAX_TOKENS),
            call_groq(_rebuttal_prompt("B", conflict, argument_a), ADVOCATE_TEMPERATURE, REBUTTAL_MAX_TOKENS),
        )

    judge_raw = await call_groq(
        _judge_prompt(
            conflict,
            argument_a,
            argument_b,
            rebuttal_a or NO_REBUTTAL_NOTE,
            rebuttal_b or NO_REBUTTAL_NOTE,
        ),
        JUDGE_TEMPERATURE,
        JUDGE_MAX_TOKENS,
    )
    verdict = parse_judge_output(judge_raw)

    winner = str(verdict.get("winner") or "FLAG").strip().upper()
    if winner not in {"A", "B", "FLAG"}:
        winner = "FLAG"

    if winner == "A":
        winning_value: str | None = str(claim_a["value"])
        base_confidence = float(claim_a.get("confidence") or 0.0)
    elif winner == "B":
        winning_value = str(claim_b["value"])
        base_confidence = float(claim_b.get("confidence") or 0.0)
    else:
        winning_value = None
        base_confidence = 0.40

    adjustment = _clamp(_to_float(verdict.get("confidence_adjustment")), -0.10, 0.10)
    final_confidence = _clamp(base_confidence + adjustment, 0.0, 1.0)

    rebuttal_assessment = verdict.get("rebuttal_assessment")
    if not isinstance(rebuttal_assessment, dict):
        rebuttal_assessment = {"A_rebuttal": "weak", "B_rebuttal": "weak"}

    return {
        "field_name": field_name,
        "winner": winner,
        "winning_value": winning_value,
        "deciding_factor": str(verdict.get("deciding_factor") or "unresolvable"),
        "reasoning": str(verdict.get("reasoning") or ""),
        "rebuttal_assessment": rebuttal_assessment,
        "argument_a": argument_a,
        "argument_b": argument_b,
        "rebuttal_a": rebuttal_a,
        "rebuttal_b": rebuttal_b,
        "final_confidence": final_confidence,
        "steps_used": 5 if rebuttals_ran else 3,
    }


def _advocate_prompt(advocate: str, conflict: dict[str, Any]) -> str:
    return ADVOCATE_PROMPT_TEMPLATE.format(
        advocate=advocate,
        authority_ranking=AUTHORITY_RANKING,
        **_shared_prompt_fields(conflict),
    )


def _rebuttal_prompt(advocate: str, conflict: dict[str, Any], opposing_argument: str) -> str:
    return REBUTTAL_PROMPT_TEMPLATE.format(
        advocate=advocate,
        opponent="B" if advocate == "A" else "A",
        opposing_argument=opposing_argument,
        permitted_angles=REBUTTAL_ANGLES_A if advocate == "A" else REBUTTAL_ANGLES_B,
        authority_ranking=AUTHORITY_RANKING,
        **_shared_prompt_fields(conflict),
    )


def _judge_prompt(
    conflict: dict[str, Any],
    argument_a: str,
    argument_b: str,
    rebuttal_a: str,
    rebuttal_b: str,
) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(
        argument_a=argument_a,
        argument_b=argument_b,
        rebuttal_a=rebuttal_a,
        rebuttal_b=rebuttal_b,
        authority_ranking=AUTHORITY_RANKING,
        **_shared_prompt_fields(conflict),
    )


def _shared_prompt_fields(conflict: dict[str, Any]) -> dict[str, Any]:
    volatility = str(conflict.get("volatility") or "HIGH").upper()
    weights = VOLATILITY_WEIGHTS.get(volatility, VOLATILITY_WEIGHTS["HIGH"])
    return {
        "field_name": conflict["field_name"],
        "volatility": volatility,
        "recency_weight": weights["recency"],
        "authority_weight": weights["authority"],
        "corroboration_weight": weights["corroboration"],
        "claim_a": _format_claim(conflict["claim_a"]),
        "claim_b": _format_claim(conflict["claim_b"]),
    }


def _format_claim(claim: dict[str, Any]) -> str:
    return CLAIM_TEMPLATE.format(
        value=claim.get("value"),
        source_url=claim.get("source_url"),
        date=claim.get("date"),
        authority=claim.get("authority"),
        corroboration=claim.get("corroboration"),
        confidence=claim.get("confidence"),
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
