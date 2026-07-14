"""Narrator stage — synthesizes a 600-900 word program brief from adjudicated field data."""

from __future__ import annotations

import logging
import os
import re
import time

import requests

from core import cost_tracker
from core.providers import provider_for_stage
from core.schemas import AgentState, BriefOutput, FieldReport, PipelineError, SchemaCoverage, new_id, now_iso


logger = logging.getLogger(__name__)


_SECTION_ORDER = [
    "program_basics",
    "earn_mechanics",
    "burn_mechanics",
    "tier_system",
    "partnerships",
    "digital_experience",
    "member_sentiment",
    "competitive_position",
]

_SECTION_LABELS = {
    "program_basics": "Program Overview",
    "earn_mechanics": "Earning",
    "burn_mechanics": "Redemption",
    "tier_system": "Tiers",
    "partnerships": "Partnerships",
    "digital_experience": "Digital Experience",
    "member_sentiment": "Member Sentiment",
    "competitive_position": "Competitive Position",
}

_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def narrator_node(state: AgentState) -> dict:
    """Generate a program brief from the post-adjudication field report."""
    field_report = state.get("field_report")
    if not field_report:
        return {
            "errors": [
                *state.get("errors", []),
                PipelineError(stage="narration", message="Narration skipped: no field report available."),
            ],
            "updated_at": now_iso(),
        }

    usable = [
        e for e in field_report.entries
        if e.value is not None and e.status in ("extracted", "flagged", "ambiguous")
    ]
    if not usable:
        return {
            "errors": [
                *state.get("errors", []),
                PipelineError(stage="narration", message="Narration skipped: field report has no extracted values."),
            ],
            "updated_at": now_iso(),
        }

    program_name = state.get("program_name") or "the program"
    brand = state.get("brand")

    try:
        brief_text = _generate_brief(field_report, program_name, brand)
    except Exception as exc:
        return {
            "errors": [
                *state.get("errors", []),
                PipelineError(stage="narration", message=str(exc)),
            ],
            "updated_at": now_iso(),
        }

    brief = BriefOutput(
        brief_id=new_id("brief"),
        run_id=state.get("run_id") or "",
        brief_text=brief_text,
        word_count=len(brief_text.split()),
    )

    coverage = SchemaCoverage(
        total_fields=len(field_report.entries) or SchemaCoverage.model_fields["total_fields"].default,
        supported_fields=field_report.extracted_count,
        manual_review_fields=field_report.ambiguous_count + field_report.flagged_count,
        null_fields=field_report.not_found_count,
        rejected_fields=0,
    )
    total = coverage.total_fields or 1
    data_quality = round(
        (coverage.supported_fields + coverage.manual_review_fields * 0.3) / total, 2
    )

    return {
        "final_brief": brief,
        "schema_coverage": coverage,
        "data_quality": data_quality,
        "updated_at": now_iso(),
    }


def _generate_brief(field_report: FieldReport, program_name: str, brand: str | None) -> str:
    """Narrate the brief with an LLM; fall back to the deterministic template.

    NARRATION_MODE=template forces the old no-LLM behaviour (also the automatic
    fallback when the LLM is unconfigured or errors).
    """
    if os.getenv("NARRATION_MODE", "llm").strip().lower() != "template":
        try:
            return _build_llm_brief(field_report, program_name, brand)
        except Exception:
            logger.exception("LLM narration failed — falling back to template brief")
    return _build_template_brief(field_report, program_name, brand)


def _render_value(value: object) -> str:
    """Render a field value for prose — lists join readably instead of repr."""
    if isinstance(value, list):
        return "; ".join(_render_value(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_render_value(v)}" for k, v in value.items())
    return str(value)


_NARRATION_PROMPT = """\
You are a senior loyalty-program analyst writing an intelligence brief on {program_label}.

Write the brief in Markdown using ONLY the extracted field data below. Absolute rules:
- Never add facts, numbers, partners, tiers, or dates that are not in the data.
- Never include URLs or links.
- If a value is marked [verify], keep a "(needs verification)" caveat next to it.
- Do not pad: skip sections with no data rather than speculating.

Structure:
1. Start with the heading "# {heading}".
2. A 2-3 sentence executive summary paragraph synthesizing the most decision-relevant facts.
3. Then one short section per data category present, in this order, using "## " headings:
   Program Overview, Earning, Redemption, Tiers, Partnerships, Digital Experience,
   Member Sentiment, Competitive Position.
4. Write flowing analyst prose (not bullet lists) — 500-800 words total.

EXTRACTED FIELD DATA:
{field_data}
"""


def _build_llm_brief(field_report: FieldReport, program_name: str, brand: str | None) -> str:
    """One LLM call that narrates the extracted fields into analyst prose."""
    lines: list[str] = []
    for section in _SECTION_ORDER:
        section_entries = [
            e for e in field_report.entries
            if e.field_path.startswith(f"{section}.") and e.value is not None and e.status != "not_found"
        ]
        if not section_entries:
            continue
        lines.append(f"[{_SECTION_LABELS.get(section, section)}]")
        for e in section_entries:
            flag = " [verify]" if e.status in ("flagged", "ambiguous") else ""
            lines.append(f"{e.field_path.split('.', 1)[-1]}: {_render_value(e.value)}{flag}")
    if not lines:
        raise ValueError("no usable field data for narration")

    brand_suffix = f" ({brand})" if brand and brand != program_name else ""
    prompt = _NARRATION_PROMPT.format(
        program_label=f"{program_name}{brand_suffix}",
        heading=f"{program_name}{brand_suffix} — Loyalty Intelligence Brief",
        field_data="\n".join(lines),
    )
    text = _call_gemini(prompt).strip()

    # Grounding guard: the brief must never carry URLs (sources are shown
    # separately in the UI); strip any the model added despite instructions.
    text = re.sub(r"\[([^\]]*)\]\(https?://[^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    if len(text.split()) < 60:
        raise ValueError(f"LLM narration too short ({len(text.split())} words)")
    return text


def _call_gemini(prompt: str, max_retries: int = 2) -> str:
    provider = provider_for_stage("narration")
    raw = os.getenv("NARRATION_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()] or ([provider.api_key] if provider.api_key else [])
    if not keys:
        raise RuntimeError("Narration: no API key configured. Set NARRATION_API_KEYS or NARRATION_API_KEY or GEMINI_API_KEY.")

    api_base = (provider.api_base or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model = provider.resolved_model or "gemini-2.5-flash"
    url = f"{api_base}/models/{model}:generateContent"

    last_error: Exception | None = None
    key_idx = 0
    for attempt in range((max_retries + 1) * len(keys)):
        response = requests.post(
            url,
            headers={"x-goog-api-key": keys[key_idx % len(keys)], "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 4096,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=120,
        )
        if response.status_code not in _TRANSIENT_STATUS_CODES:
            response.raise_for_status()
            payload = response.json()
            usage = payload.get("usageMetadata", {})
            ledger = cost_tracker.get_current_ledger()
            if ledger:
                ledger.record_gemini(
                    "narration",
                    int(usage.get("promptTokenCount") or 0),
                    int(usage.get("candidatesTokenCount") or 0),
                )
            return payload["candidates"][0]["content"]["parts"][0]["text"]

        last_error = requests.HTTPError(
            f"Narration LLM returned {response.status_code}", response=response
        )
        if response.status_code == 429:
            key_idx += 1
        else:
            time.sleep(2 ** min(attempt, 4))

    raise last_error or RuntimeError("Narration LLM request failed.")


def _build_template_brief(field_report: FieldReport, program_name: str, brand: str | None) -> str:
    """Build a structured prose brief directly from extracted field data — no LLM call."""
    by_section: dict[str, dict[str, str]] = {}
    for entry in field_report.entries:
        if entry.value is None or entry.status == "not_found":
            continue
        section = entry.field_path.split(".")[0]
        field = entry.field_path.split(".", 1)[-1].replace("_", " ").title()
        flag = " *(verify)*" if entry.status in ("flagged", "ambiguous") else ""
        by_section.setdefault(section, {})[field] = f"{_render_value(entry.value)}{flag}"

    brand_suffix = f" ({brand})" if brand and brand != program_name else ""
    paragraphs = [f"# {program_name}{brand_suffix} — Loyalty Intelligence Brief\n"]

    section_intros = {
        "program_basics": "**Program Overview.**",
        "earn_mechanics": "**Earning.**",
        "burn_mechanics": "**Redemption.**",
        "tier_system": "**Tier Structure.**",
        "partnerships": "**Partnerships.**",
        "digital_experience": "**Digital Experience.**",
        "member_sentiment": "**Member Sentiment.**",
        "competitive_position": "**Competitive Position.**",
    }

    for section in _SECTION_ORDER:
        fields = by_section.get(section)
        if not fields:
            continue
        label = section_intros.get(section, f"**{section.replace('_',' ').title()}.**")
        lines = [f"- {k}: {v}" for k, v in fields.items()]
        paragraphs.append(f"{label}\n" + "\n".join(lines))

    for section, fields in by_section.items():
        if section not in _SECTION_ORDER:
            label = f"**{section.replace('_',' ').title()}.**"
            lines = [f"- {k}: {v}" for k, v in fields.items()]
            paragraphs.append(f"{label}\n" + "\n".join(lines))

    if len(paragraphs) == 1:
        paragraphs.append("*No extracted data available for this program.*")

    return "\n\n".join(paragraphs)


