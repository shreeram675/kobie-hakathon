"""Structured, source-traceable JSON export of a run's final analyst output.

Builds a flat export from the pipeline's existing FieldReport / BriefOutput /
ComparisonBrief data — every value ships with the source_url(s) and confidence
that were already tracked during adjudication (core/schemas.py), so nothing
here is re-derived or guessed. Operates on the same serialized response dict
returned by GET /api/run/{run_id}, so it works for live, cached, and
DB-restored runs alike.
"""
from __future__ import annotations

from typing import Any

EXPORT_SCHEMA_VERSION = "1.0"


def _field_entries_export(field_report: dict[str, Any] | None) -> dict[str, Any]:
    """One key per field_path -> {value, source_urls, confidence, ...}."""
    fields: dict[str, Any] = {}
    for entry in (field_report or {}).get("entries", []) or []:
        field_path = entry.get("field_path")
        if not field_path:
            continue
        fields[field_path] = {
            "category": entry.get("category"),
            "value": entry.get("value"),
            "status": entry.get("status"),
            "source_urls": entry.get("source_urls") or [],
            "confidence": entry.get("confidence"),
            "corroboration_count": entry.get("corroboration_count", 0),
            "conflict_type": entry.get("conflict_type"),
            "rejected_alternatives": entry.get("rejected_alternatives") or [],
            "all_values": entry.get("all_values"),
        }
    return fields


def _brief_export(
    final_brief: dict[str, Any] | None,
    field_report: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not final_brief:
        return None
    # cited_claim_ids isn't populated by the narrator today (narration synthesizes
    # prose from the whole field report rather than citing sentence-by-sentence),
    # so fall back to the union of every source URL backing that field report.
    cited = final_brief.get("cited_claim_ids") or []
    source_urls: list[str] = []
    seen: set[str] = set()
    for entry in (field_report or {}).get("entries", []) or []:
        for url in entry.get("source_urls") or []:
            if url not in seen:
                seen.add(url)
                source_urls.append(url)
    return {
        "text": final_brief.get("brief_text"),
        "word_count": final_brief.get("word_count"),
        "cited_claim_ids": cited,
        "source_urls": source_urls,
    }


def _program_export(state: dict[str, Any]) -> dict[str, Any]:
    field_report = state.get("field_report")
    return {
        "program_name": state.get("program_name"),
        "brand": state.get("brand"),
        "domain": state.get("domain"),
        "country_or_region": state.get("country_or_region"),
        "data_quality": state.get("data_quality"),
        "fields": _field_entries_export(field_report),
        "brief": _brief_export(state.get("final_brief"), field_report),
    }


def _comparison_export(response: dict[str, Any]) -> dict[str, Any] | None:
    brief = response.get("comparison_brief")
    if not brief:
        return None
    return {
        "programs": brief.get("programs") or [],
        "overall_winner": brief.get("overall_winner"),
        "executive_summary": brief.get("executive_summary"),
        "category_verdicts": [
            {
                "category": v.get("category"),
                "label": v.get("label"),
                "winner": v.get("winner"),
                "insight": v.get("insight"),
                "source_urls": v.get("source_urls") or [],
            }
            for v in brief.get("category_verdicts") or []
        ],
        "key_differentiators": [
            {
                "topic": d.get("topic"),
                "insight": d.get("insight"),
                "advantage": d.get("advantage"),
                "source_urls": d.get("source_urls") or [],
                "rejected_note": d.get("rejected_note"),
            }
            for d in brief.get("key_differentiators") or []
        ],
        "strategic_profiles": brief.get("strategic_profiles") or [],
        "differentiation_themes": brief.get("differentiation_themes") or [],
        "personas": brief.get("personas") or [],
    }


def build_export(response: dict[str, Any]) -> dict[str, Any]:
    """Build the structured JSON export for a run's serialized response dict.

    Every extracted field becomes a `field_path -> {value, source_urls,
    confidence, ...}` entry; every narrative or comparison insight carries the
    source_urls it was derived from, so all output is traceable to evidence.
    """
    export: dict[str, Any] = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "run_id": response.get("run_id"),
        "mode": response.get("mode"),
        "status": response.get("status"),
        "generated_at": response.get("updated_at") or response.get("created_at"),
        "data_quality": response.get("data_quality"),
    }

    if response.get("mode") == "compare":
        program_a = _program_export(response)
        compare_b = response.get("compare_b")
        program_b = _program_export(compare_b) if compare_b else None
        export["programs"] = [p for p in (program_a, program_b) if p is not None]
        export["comparison"] = _comparison_export(response)
    else:
        export["program"] = _program_export(response)

    return export
