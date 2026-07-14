"""LLM-backed input validation and canonical loyalty program resolution."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Protocol

import requests

from core import cost_tracker
from core.providers import provider_for_stage
from core.schemas import ClarificationOption, ProgramIdentity, SearchContext, ValidationResult


logger = logging.getLogger(__name__)

# Returns True (program corroborated by search), False (no evidence it exists),
# or None (corroboration unavailable — no key, network error, etc.).
Corroborator = Callable[[str], bool | None]


_INJECTION_PATTERN = re.compile(
    r"(?i)(ignore\s+(previous|all)\s+instructions|you\s+are\s+now\s+a|"
    r"disregard\s+the\s+above|new\s+persona|act\s+as\s+if|"
    r"system\s*:\s*you\s+are|new\s+instructions\s*:)",
)


def _contains_prompt_injection(text: str) -> bool:
    return bool(_INJECTION_PATTERN.search(text))


INPUT_VERIFIER_SYSTEM_PROMPT = """
You are the Input Validation Agent for Kobie — a professional loyalty program
intelligence platform used by loyalty consultants, program managers, and strategy
teams.

Your sole job is to identify the exact loyalty program the user wants to research
and return it as a structured identity. Do this as quickly as possible with no
unnecessary back-and-forth.

═══════════════════════════════════════════════════════
RESOLUTION APPROACH
═══════════════════════════════════════════════════════

Use your training knowledge to identify the loyalty program. Do NOT claim to
be performing a live web search — you have no search tool. For every input:

  1. Recall real loyalty programs that match the input from your training data
  2. Evaluate confidence based on how well-known and unambiguous the program is
  3. Decide: resolve, clarify, or reject

IMPORTANT: official_domain must only be set when you are highly confident it
is correct. If there is any doubt, set it to null rather than guessing.

═══════════════════════════════════════════════════════
DECISION PRIORITY ORDER
═══════════════════════════════════════════════════════

STEP 1 — RESOLVE DIRECTLY (confidence ≥ 0.90)
If the input matches a single clear loyalty program you know from training
data, return "resolved" immediately. Do not ask questions.

STEP 2 — SHOW POSSIBLE MATCHES (before asking any question)
If 2–5 real programs you know could match, return "needs_clarification"
with a populated "possible_matches" list. Add a follow_up_question only if it
meaningfully narrows the list.

STEP 3 — ASK A QUESTION (last resort)
Only when matches exceed 5 or no clear match exists and one targeted question
would narrow it significantly.

  - Ask targeted clarification questions with clear options where possible
  - Do not repeat or rephrase the same question
  - Maximum 3 follow-up questions across the entire conversation
  - After 3 failed attempts, reject gracefully with a clear explanation of
    what information is needed (company name, region, official website, etc.)

═══════════════════════════════════════════════════════
ANTI-HALLUCINATION RULES
═══════════════════════════════════════════════════════
- Never invent a loyalty program, brand, company, or domain
- Only return "resolved" for a real loyalty program you are confident exists
- Do not fabricate programs by appending Rewards, Club, Points, Plus to input
- If input is fictional, nonsensical, or unrelated to loyalty, return "rejected"
- User confirmation cannot make a fictional or unverified program real
- Always prioritize accuracy over assumptions

═══════════════════════════════════════════════════════
DOMAIN AND REGION — ALWAYS REQUIRED, NEVER OMIT
═══════════════════════════════════════════════════════

domain (required — pick the single most specific match; never null or "Other"
  for well-known programs)

  Airline            — programs run by airlines (frequent flyer, miles)
  Hotel              — programs run by hotel chains
  Retail             — physical or mixed retail (department stores, fashion, electronics)
  Banking/Credit Card — bank-issued or co-brand credit card programs
  Coalition          — multi-brand / multi-partner programs (Aeroplan, Nectar, Payback)
  Telecom            — mobile operators, internet providers
  Fuel               — petrol station / gas station programs
  E-commerce         — online-only retail (Amazon, Flipkart)
  Food & Beverage    — cafes, restaurants, QSR chains (Starbucks, Dunkin', McDonald's)
  Food Delivery      — meal-delivery platforms (DoorDash, Swiggy, Zomato)
  Healthcare         — pharmacies, health insurance, hospital networks
  Entertainment      — streaming, cinemas, gaming, sports clubs
  Education          — ed-tech platforms, universities
  Mobility           — ride-hailing, car rental, EV charging (Uber, Hertz)
  Fintech            — digital wallets, BNPL, neobanks (without a physical card)
  Supermarket        — grocery chains and hypermarkets
  Other              — only when no category above fits at all

  Classification rules:
  • Use the primary business of the sponsoring BRAND, not the rewards mechanic.
  • Airlines with co-brand cards → Airline (aviation is the primary business).
  • Banks that issue airline miles → Banking/Credit Card.
  • Grocery stores with fuel rewards → Supermarket.
  • Never return "Other" for a well-known program — find the correct category.

country_or_region (required — always set; never null or empty)
  The primary country or geographic region where the program operates.
  Write the full English name — no abbreviations (not "US", write "United States").
  Examples: "United States", "United Kingdom", "India", "Canada", "Australia",
  "Germany", "France", "Singapore", "UAE", "South Africa", "Brazil".
  Use "Global" only if the program has no dominant home market.
  When a program is primarily associated with one country (even if
  internationally available), always use that country.

═══════════════════════════════════════════════════════
OUTPUT FORMAT — valid JSON only, no Markdown fences
═══════════════════════════════════════════════════════

Resolved:
{
  "status": "resolved",
  "program_name": "Dunkin' Rewards",
  "brand": "Dunkin'",
  "domain": "Food & Beverage",
  "country_or_region": "United States",
  "confidence": 0.97,
  "official_domain": "dunkinrewards.com",
  "noise_exclude_terms": [],
  "search_context": {
    "program_type": "points-based",
    "entity_disambiguation": "consumer loyalty app, not Dunkin Donuts franchise operations"
  }
}

Needs clarification:
{
  "status": "needs_clarification",
  "possible_matches": [
    {
      "program_name": "United MileagePlus",
      "brand": "United Airlines",
      "domain": "Airline",
      "official_domain": "mileageplus.com"
    },
    {
      "program_name": "United Supermarkets MyMixx",
      "brand": "United Supermarkets",
      "domain": "Supermarket",
      "official_domain": "unitedtexas.com"
    }
  ],
  "follow_up_questions": ["Are you looking for an airline or grocery program?"],
  "confidence": 0.60
}

Rejected:
{
  "status": "rejected",
  "confidence": 0,
  "reason": "Could not identify a real loyalty program from the input provided.",
  "missing_info": "Please provide the company name, region, or official website to help identify the program."
}

═══════════════════════════════════════════════════════
OUTPUT FIELDS
═══════════════════════════════════════════════════════

domain (string) — REQUIRED in every resolved response
  Must be exactly one of the allowed values:
  Airline, Hotel, Retail, Banking/Credit Card, Coalition, Telecom,
  Fuel, E-commerce, Food & Beverage, Food Delivery, Healthcare,
  Entertainment, Education, Mobility, Fintech, Supermarket, Other.
  Never leave this field null or empty. If no better fit exists, use "Other".

country_or_region (string) — REQUIRED in every resolved response
  The primary country or region where this loyalty program operates.
  Use the full English country name (e.g. "United States", "United Kingdom",
  "India", "Australia", "Canada", "Germany", "Singapore").
  For multi-country programs use the region (e.g. "Global", "Europe",
  "Southeast Asia"). Never leave this field null or empty — default to
  "Global" only when the program genuinely operates across many countries
  with no dominant home market.

official_domain (string)
  The program's primary web domain for T&C and FAQ pages.
  Only populate when you are highly confident — set null if uncertain.

noise_exclude_terms (array of strings)
  Keywords to add as negatives in Tavily queries to strip irrelevant results.
  Populate based on your knowledge of the brand's other business lines,
  subsidiaries, or corporate entities that share the same name.
  Leave empty [] if no noise risk detected.

search_context.program_type (string)
  One of: "points-based", "miles-based", "cashback", "subscription",
  "tiered-benefits", "coalition"

search_context.entity_disambiguation (string)
  One sentence describing what this program IS and what it is NOT.
  Critical for conglomerates or brands where corporate and consumer entities
  share a name.

program_subtype (optional)
  Set to "B2B" only for corporate-facing programs. Omit otherwise.
""".strip()


class ChatClient(Protocol):
    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Return the assistant response parsed as JSON."""


class OpenAICompatibleChatClient:
    """Small OpenAI-compatible chat-completions client.

    Configure with:
    - INPUT_VERIFIER_API_BASE, for example https://api.openai.com/v1/chat/completions
    - INPUT_VERIFIER_API_KEY
    - INPUT_VERIFIER_MODEL
    """

    def __init__(self) -> None:
        provider = provider_for_stage("validation")
        self.api_base = provider.api_base
        self.api_key = provider.api_key
        self.model = provider.resolved_model

    MAX_ATTEMPTS = 4
    MAX_RETRY_SLEEP_SECONDS = 15.0

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.api_base or not self.api_key or not self.model:
            raise RuntimeError(
                "Input verifier LLM is not configured. Set INPUT_VERIFIER_API_BASE, "
                "INPUT_VERIFIER_API_KEY, and INPUT_VERIFIER_MODEL."
            )

        response = None
        for attempt in range(self.MAX_ATTEMPTS):
            response = requests.post(
                self.api_base,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=45,
            )
            if response.status_code not in (429, 500, 502, 503, 504) or attempt == self.MAX_ATTEMPTS - 1:
                break
            # Prefer the provider's suggested wait ("try again in 7.66s"),
            # otherwise back off exponentially; cap so a daily-quota 429 with a
            # huge retry-after cannot stall the run.
            match = re.search(r"try again in ([0-9.]+)s", response.text)
            delay = float(match.group(1)) + 0.5 if match else 2.0 * (attempt + 1)
            delay = min(delay, self.MAX_RETRY_SLEEP_SECONDS)
            logger.warning(
                "Input verifier got HTTP %s (attempt %d/%d), retrying in %.1fs",
                response.status_code, attempt + 1, self.MAX_ATTEMPTS, delay,
            )
            time.sleep(delay)

        assert response is not None
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        ledger = cost_tracker.get_current_ledger()
        if ledger and (usage.get("prompt_tokens") or usage.get("completion_tokens")):
            ledger.record_gemini("validation", int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))
        content = payload["choices"][0]["message"]["content"]
        return parse_json_content(content)


def parse_json_content(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def validate_input(
    user_input: str,
    chat_client: ChatClient | None = None,
    corroborator: Corroborator | None = None,
) -> ValidationResult:
    if not user_input.strip():
        return ValidationResult(status="rejected", confidence=0, reason="Input is empty.")

    return validate_conversation(
        [{"role": "user", "content": user_input.strip()}],
        chat_client=chat_client,
        corroborator=corroborator,
    )


def validate_conversation(
    messages: list[dict[str, str]],
    chat_client: ChatClient | None = None,
    corroborator: Corroborator | None = None,
) -> ValidationResult:
    user_messages = [message["content"].strip() for message in messages if message.get("role") == "user" and message.get("content", "").strip()]
    if not user_messages:
        return ValidationResult(status="rejected", confidence=0, reason="Input is empty.")

    if any(_contains_prompt_injection(m) for m in user_messages):
        return ValidationResult(
            status="rejected",
            confidence=0,
            reason="Input contains disallowed content. Please enter a loyalty program name.",
        )

    client = chat_client or OpenAICompatibleChatClient()
    try:
        raw_result = client.complete_json(
            [
                {"role": "system", "content": INPUT_VERIFIER_SYSTEM_PROMPT},
                *messages,
            ]
        )
    except Exception:
        logger.exception("Input verifier LLM call failed")
        return ValidationResult(
            status="needs_clarification",
            confidence=0,
            follow_up_questions=["Which loyalty program should Kobie research?"],
            reason=(
                "The input verifier is temporarily unavailable (provider error or rate limit). "
                "Please try again in a moment."
            ),
        )

    return _parse_verifier_output(
        user_input=" | ".join(user_messages),
        payload=raw_result,
        corroborator=corroborator,
    )


def _parse_verifier_output(
    user_input: str,
    payload: dict[str, Any],
    corroborator: Corroborator | None = None,
) -> ValidationResult:
    status = payload.get("status")
    confidence = float(payload.get("confidence", 0))

    if status == "rejected":
        return ValidationResult(
            status="rejected",
            confidence=0,
            reason=str(payload.get("reason") or "Could not identify a real loyalty program from the input provided."),
            missing_info=payload.get("missing_info") or None,
        )

    if status == "resolved" and confidence >= 0.90:
        if _needs_existence_check(user_input, payload):
            corroborated = (corroborator or _search_corroboration)(str(payload.get("program_name") or ""))
            if corroborated is False:
                return ValidationResult(
                    status="rejected",
                    confidence=0,
                    reason="Could not verify that this loyalty program exists. Please check the program name or provide the company's official website.",
                )
            if corroborated is None and _looks_like_unknown_or_fictional_input(user_input) and _looks_like_synthetic_program_name(user_input, payload):
                # Corroboration unavailable — fall back to the heuristic guard.
                return ValidationResult(
                    status="rejected",
                    confidence=0,
                    reason="Could not identify a real loyalty program from the input provided.",
                )
        raw_sc = payload.get("search_context")
        search_context = None
        if isinstance(raw_sc, dict):
            search_context = SearchContext(
                program_type=raw_sc.get("program_type"),
                entity_disambiguation=raw_sc.get("entity_disambiguation"),
            )
        raw_domain = payload.get("domain")
        raw_region = payload.get("country_or_region")
        identity = ProgramIdentity(
            raw_input=user_input,
            program_name=str(payload["program_name"]),
            brand=str(payload.get("brand") or payload["program_name"]),
            domain=normalize_domain(raw_domain) if raw_domain else "Other",
            country_or_region=str(raw_region).strip() if raw_region else "Global",
            program_subtype=_parse_program_subtype(payload.get("program_subtype"), str(payload["program_name"])),
            confidence=confidence,
            official_domain=payload.get("official_domain") or None,
            noise_exclude_terms=[str(t) for t in (payload.get("noise_exclude_terms") or [])],
            search_context=search_context,
        )
        return ValidationResult(status="resolved", confidence=confidence, identity=identity)

    possible_matches = [
        ClarificationOption(
            program_name=str(match["program_name"]),
            brand=str(match.get("brand") or match["program_name"]),
            domain=normalize_domain(match.get("domain")),
            official_domain=match.get("official_domain") or None,
        )
        for match in payload.get("possible_matches", [])
        if isinstance(match, dict)
        and "program_name" in match
        and "domain" in match
        and not _looks_like_synthetic_program_name(user_input, match)
    ]
    follow_ups = [str(question) for question in payload.get("follow_up_questions", [])][:3]
    if not possible_matches and _looks_like_unknown_or_fictional_input(user_input):
        return ValidationResult(
            status="rejected",
            confidence=0,
            reason="No known loyalty program exists for this input.",
        )
    if not follow_ups:
        follow_ups = ["Which exact loyalty program should Kobie research?"]

    return ValidationResult(
        status="needs_clarification",
        confidence=min(confidence, 0.89),
        possible_matches=possible_matches,
        follow_up_questions=follow_ups,
        reason="Input verifier confidence is below 0.90.",
    )


def _parse_program_subtype(llm_value: object, program_name: str) -> str | None:
    """Detect B2B vs B2C from LLM output, with a deterministic keyword fallback."""
    raw = str(llm_value or "").strip().upper()
    if raw in {"B2B", "CORPORATE", "BUSINESS"}:
        return "B2B"
    if raw in {"B2C", "CONSUMER", "PERSONAL", "INDIVIDUAL"}:
        return "B2C"
    # Deterministic fallback: common B2B signals in program names across any domain.
    # The LLM is the primary detector; this handles cases where the LLM omits program_subtype.
    name_lower = program_name.lower()
    b2b_signals = (
        "for business",
        "corporate",
        " b2b",
        "business extra",
        "business rewards",
        "perksplus",
        " sme ",
        "enterprise program",
    )
    if any(signal in name_lower for signal in b2b_signals):
        return "B2B"
    # Programs whose name ends with the bare word "business" (e.g. "AAdvantage Business")
    if name_lower.rstrip().endswith(" business"):
        return "B2B"
    return None


def normalize_domain(value: object) -> str:
    normalized = " ".join(str(value or "Other").replace("_", " ").split())
    return normalized[:80] if normalized else "Other"


def verifier_result_as_message(result: ValidationResult) -> dict[str, str]:
    return {
        "role": "assistant",
        "content": json.dumps(result.model_dump(), ensure_ascii=True),
    }


_SYNTHETIC_SUFFIXES = (" rewards", " loyalty", " club", " points", " plus", " membership")


def _needs_existence_check(user_input: str, payload: dict[str, Any]) -> bool:
    """Decide whether a resolved program is suspicious enough to corroborate.

    Generic-suffix names ("X Rewards") are exactly the shape LLMs hallucinate by
    appending a suffix to whatever the user typed, so those get one cheap search
    before a full pipeline run is committed. Distinctive names (e.g. "Marriott
    Bonvoy") skip the check to avoid spending search credits on every run.
    """
    program_name = str(payload.get("program_name") or "").lower()
    if any(program_name.endswith(suffix) for suffix in _SYNTHETIC_SUFFIXES):
        return True
    return _looks_like_unknown_or_fictional_input(user_input)


# Generic loyalty vocabulary — carries no signal about WHICH program a page covers.
_GENERIC_NAME_TOKENS = frozenset(
    {"rewards", "reward", "loyalty", "club", "points", "plus", "membership", "member", "program", "card", "the", "my"}
)
_LOYALTY_CONTEXT_TOKENS = frozenset(
    {"loyalty", "reward", "rewards", "points", "member", "members", "membership", "miles", "cashback", "perks", "program"}
)


def _search_corroboration(program_name: str) -> bool | None:
    """One Tavily search to confirm the resolved program actually exists.

    A result corroborates the program when its title/URL contains every
    distinctive token of the name (generic words like "rewards" excluded —
    official names often differ, e.g. "Best Buy Rewards" vs "My Best Buy")
    AND the same result shows loyalty-program context. Returns True/False,
    or None when corroboration is unavailable (no key, network error).
    """
    if not program_name.strip():
        return None
    try:
        from pipeline.stages.retrieval import TavilyRestClient

        client = TavilyRestClient()
        if not client.api_key:
            return None
        results = client.search(f'"{program_name}" loyalty program', max_results=5)
    except Exception:
        logger.exception("Corroboration search failed for %r — skipping check", program_name)
        return None

    all_tokens = re.findall(r"[a-z0-9]+", program_name.lower())
    distinctive = [t for t in all_tokens if t not in _GENERIC_NAME_TOKENS] or all_tokens
    for result in results:
        identity_blob = " ".join(str(result.get(key) or "") for key in ("title", "url")).lower()
        context_blob = (identity_blob + " " + str(result.get("content") or "").lower())
        context_tokens = set(re.findall(r"[a-z0-9]+", context_blob))
        if all(token in identity_blob for token in distinctive) and context_tokens & _LOYALTY_CONTEXT_TOKENS:
            return True
    return False


def _looks_like_synthetic_program_name(user_input: str, payload: dict[str, Any]) -> bool:
    program_name = str(payload.get("program_name") or "").lower()
    brand = str(payload.get("brand") or "").lower()
    user_text = user_input.lower()

    if not any(program_name.endswith(suffix) for suffix in _SYNTHETIC_SUFFIXES):
        return False
    if program_name in user_text:
        return False

    brand_tokens = set(re.findall(r"[a-z0-9]+", brand))
    user_tokens = set(re.findall(r"[a-z0-9]+", user_text))
    if brand_tokens and brand_tokens.issubset(user_tokens):
        known_brands = {
            "american express",
            "amex",
            "air india",
            "marriott",
            "hilton",
            "british airways",
        }
        return brand not in known_brands
    return False


def _looks_like_unknown_or_fictional_input(user_input: str) -> bool:
    text = user_input.lower()
    suspicious_terms = {
        "cockroach",
        "janata party",
        "fake",
        "imaginary",
        "fictional",
        "asdf",
        "qwerty",
    }
    return any(term in text for term in suspicious_terms)
