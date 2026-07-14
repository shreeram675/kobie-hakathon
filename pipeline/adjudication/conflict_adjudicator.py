"""Conflict adjudicator node: detect disagreeing claims and resolve them.

Runs after extraction/normalization. Equivalent values auto-resolve, merge-type
fields (range/union/recency/majority_vote) resolve deterministically, and
single-truth fields with a decisive confidence gap (> 0.20) auto-resolve to the
stronger claim; remaining close calls go through the 5-step adversarial debate
engine. The logic is program-agnostic — every
value, source, and date comes from the pipeline state, never from the model.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime
import json
import re
from typing import Any

from core.schemas import AgentState, FieldReport, NormalizedObjectPacket, RawDocument, new_id, now_iso
from pipeline.adjudication.debate_engine import classify_conflict_type, run_debate


AUTO_RESOLVE_SCORE_GAP = 0.20
FLAG_CONFIDENCE = 0.40
FLAG_TEXT = "CONFLICTING SOURCES — verify manually"

# ── Field-type strategy map ────────────────────────────────────────────────────
# Fields whose conflicts should be resolved by a deterministic strategy rather
# than adversarial debate. Any field not listed defaults to "debate".
#
# range        → keep a [min–max] span (earn rates that can vary by category)
# union        → deduplicated union of all values (partner lists, bonus categories)
# recency      → keep the most recent value (dates, expiry policies)
# majority_vote→ most-common value across sources (boolean flags, categorical)
# debate       → adversarial 5-step debate (single-truth numeric facts)

FIELD_STRATEGY_MAP: dict[str, str] = {
    # earn mechanics — rates can differ by category, so keep the range
    "base_earn_rate": "range",
    "earn_rate_base": "range",
    "earn_rate_unit": "range",
    "bonus_categories": "union",
    "co_brand_card_earn": "range",
    "partner_earn": "range",
    # partnerships — more sources = more complete list
    "partner_names": "union",
    "discontinued_partners": "union",
    "earn_details": "union",
    "burn_details": "union",
    # dates / expiry — take the most recent
    "expiry_policy": "recency",
    "blackout_or_capacity_rules": "recency",
    "qualification_period": "recency",
    # booleans — majority rules
    "mobile_app_available": "majority_vote",
    # transfer ratios are single-truth facts — debate
    "transfer_ratios": "debate",
    "point_value_cpp": "debate",
    "cpp": "debate",
    "redemption_thresholds": "debate",
    "redemption_value": "debate",
}

# Universal volatility classification by field-path suffix, falling back to
# the section. Matches the ArcGuide AG-8 volatility split.
HIGH_VOLATILITY_FIELD_NAMES = frozenset(
    {
        "earn_rate_base",
        "base_earn_rate",
        "earn_rate_unit",
        "tier_thresholds",
        "redemption_value",
        "redemption_thresholds",
        "point_value_cpp",
        "cpp",
        "app_ratings",
        "ratings",
        "recent_changes_last_6_months",
    }
)
LOW_VOLATILITY_FIELD_NAMES = frozenset(
    {
        "program_name",
        "program_type",
        "founding_year",
        "tier_names",
        "brand",
        "industry",
        "geography",
    }
)
HIGH_VOLATILITY_SECTIONS = frozenset(
    {"earn_mechanics", "burn_mechanics", "partnerships", "digital_experience", "member_sentiment"}
)

# Map pipeline source_type vocabulary (current and legacy) to debate authority tiers.
SOURCE_TYPE_TO_AUTHORITY = {
    "official": "official",
    "terms": "official",
    "faq": "official",
    "partners": "official",
    "financial": "major_publication",
    "news": "news",
    "review": "aggregator",
    "valuation": "aggregator",
    "app_reviews": "aggregator",
    "competitors": "aggregator",
    "forum": "forum",
    "forums": "forum",
}
DEFAULT_AUTHORITY = "aggregator"

# URL path segments that strongly signal a page is about a specific product category.
# These are used to detect when a source URL is clearly off-topic for the programme domain.
_CATEGORY_PATH_SIGNALS: dict[str, frozenset[str]] = {
    "credit_card": frozenset({
        "/credit-card", "/credit-cards", "/creditcard", "/cards/credit",
        "/secured-card", "/best-cards", "/credit-score",
    }),
    "airline_miles": frozenset({
        "/frequent-flyer", "/airline-miles", "/airline-rewards",
        "/award-chart", "/mileage-program", "/airline-loyalty",
    }),
    "hotel_rewards": frozenset({
        "/hotel-rewards", "/hotel-loyalty", "/hotel-points", "/hotel-status",
    }),
    "mortgage_banking": frozenset({
        "/mortgage", "/home-loan", "/refinance", "/personal-loan", "/savings-account",
    }),
    "insurance": frozenset({
        "/health-insurance", "/car-insurance", "/life-insurance", "/term-insurance",
    }),
    "grocery_retail": frozenset({
        "/grocery-rewards", "/supermarket-loyalty", "/store-card",
    }),
    "ride_hailing": frozenset({
        "/ride-hailing", "/cab-booking", "/taxi-rewards",
    }),
}

# For each programme domain, which path-signal categories are clearly off-topic?
# Covers every loyalty programme domain the input validator can produce.
_OFFTOPIC_SIGNALS_FOR_DOMAIN: dict[str, frozenset[str]] = {
    "airline":             frozenset({"credit_card", "hotel_rewards", "mortgage_banking", "insurance", "grocery_retail", "ride_hailing"}),
    "hotel":               frozenset({"credit_card", "airline_miles", "mortgage_banking", "insurance", "grocery_retail", "ride_hailing"}),
    "retail":              frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "banking/credit card": frozenset({"airline_miles", "hotel_rewards", "mortgage_banking", "insurance", "grocery_retail", "ride_hailing"}),
    "coalition":           frozenset({"mortgage_banking", "insurance"}),
    "telecom":             frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "fuel":                frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "e-commerce":          frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "food & beverage":     frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "food delivery":       frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "healthcare":          frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking"}),
    "entertainment":       frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "education":           frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "mobility":            frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance", "grocery_retail"}),
    "fintech":             frozenset({"airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
    "supermarket":         frozenset({"credit_card", "airline_miles", "hotel_rewards", "mortgage_banking", "insurance"}),
}


def _dampen_authority_for_domain(
    authority: str,
    source_url: str | None,
    program_domain: str,
    program_name: str = "",
    brand: str = "",
) -> str:
    """Lower authority when a URL path clearly signals an off-topic product category.

    Works for every programme domain type — the check uses the URL path against a
    per-domain off-topic signal map, not a hardcoded pair of allowed domains.
    Only "official" and "major_publication" authority levels are candidates for
    downgrade; aggregator/forum/news are already low-authority and unaffected.
    """
    if not source_url or authority not in {"official", "major_publication"}:
        return authority

    domain_lower = program_domain.lower()
    offtopic_categories = _OFFTOPIC_SIGNALS_FOR_DOMAIN.get(domain_lower)
    if not offtopic_categories:
        return authority

    path = source_url.lower()
    for prefix in ("https://", "http://"):
        if path.startswith(prefix):
            path = path[len(prefix):]
    path = "/" + "/".join(path.split("/")[1:])  # strip host, keep /path...

    for category in offtopic_categories:
        signals = _CATEGORY_PATH_SIGNALS.get(category, frozenset())
        if any(sig in path for sig in signals):
            return "aggregator"

    return authority


def _classify_field_strategy(field_name: str) -> str:
    suffix = field_name.split(".")[-1].lower()
    return FIELD_STRATEGY_MAP.get(suffix, "debate")


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _normalize_value_text(value: Any) -> str:
    """Canonicalize a claim value for equality checks only (never for display).

    Lowercases, collapses whitespace, strips thousands separators, and
    canonicalizes numeric tokens so "1.50" == "1.5" and "1,000" == "1000".
    """
    text = " ".join(str(value or "").strip().lower().split())
    text = re.sub(r"[™®©]", "", text)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return _NUMBER_RE.sub(lambda m: format(float(m.group(0)), "g"), text)


def _display_text(value: Any) -> str:
    """Render a claim value for display — lists join readably, never Python repr."""
    if isinstance(value, list):
        return ", ".join(_display_text(item) for item in value)
    return str(value) if value is not None else ""


def _values_equivalent(value_a: Any, value_b: Any) -> bool:
    normalized_a = _normalize_value_text(value_a)
    return normalized_a != "" and normalized_a == _normalize_value_text(value_b)


def _resolve_range(_field_name: str, groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple numeric/rate values into a range entry."""
    values = [str(g["value"]) for g in groups]
    all_urls = list({url for g in groups for url in g.get("source_urls", set())})
    try:
        numbers = [float(v.strip()) for v in values]
        merged = (
            f"{format(min(numbers), 'g')}–{format(max(numbers), 'g')}"
            if len(set(numbers)) > 1
            else format(numbers[0], "g")
        )
    except ValueError:
        merged = " / ".join(values) if len(values) > 1 else values[0]
    confidence = max(float(g.get("confidence") or 0.0) for g in groups)
    return {
        "value": merged,
        "source_urls": all_urls,
        "confidence": confidence,
        "all_values": [
            {"value": _display_text(g["value"]), "source_url": _best_url(g["source_urls"]), "context": None}
            for g in groups
        ],
        "conflict_type": "range",
        "strategy": "range",
    }


def _resolve_union(_field_name: str, groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Union all values across sources, deduplicated on normalized text.

    List values are flattened into individual items so "['a', 'b']" never
    renders as a Python repr, and normalization folds case/™ so
    "My Best Buy Plus™" and "my best buy plus" merge into one item.
    """
    seen: set[str] = set()
    merged_items: list[str] = []
    for g in groups:
        items = g["value"] if isinstance(g["value"], list) else [g["value"]]
        for item in items:
            val = str(item)
            key = _normalize_value_text(val)
            if key and key not in seen:
                seen.add(key)
                merged_items.append(val)
    all_urls = list({url for g in groups for url in g.get("source_urls", set())})
    confidence = max(float(g.get("confidence") or 0.0) for g in groups)
    return {
        "value": ", ".join(merged_items),
        "source_urls": all_urls,
        "confidence": confidence,
        "all_values": [
            {"value": _display_text(g["value"]), "source_url": _best_url(g["source_urls"]), "context": None}
            for g in groups
        ],
        "conflict_type": "union",
        "strategy": "union",
    }


def _resolve_recency(_field_name: str, groups: list[dict[str, Any]], documents_by_url: dict[str, Any]) -> dict[str, Any]:
    """Keep the most recently sourced value; break same-day ties by confidence.

    Documents fetched in the same run share a retrieved_at date, so without the
    confidence tiebreak this would pick an arbitrary group.
    """
    def _recency_key(g: dict[str, Any]) -> tuple[date, float]:
        url = _best_url(g["source_urls"])
        doc = documents_by_url.get(url) if url else None
        return (_document_date(doc), float(g.get("confidence") or 0.0))

    best = max(groups, key=_recency_key)
    all_urls = list({url for g in groups for url in g.get("source_urls", set())})
    return {
        "value": _display_text(best["value"]),
        "source_urls": all_urls,
        "confidence": float(best.get("confidence") or 0.0),
        "all_values": [
            {"value": _display_text(g["value"]), "source_url": _best_url(g["source_urls"]), "context": None}
            for g in groups
        ],
        "conflict_type": "recency",
        "strategy": "recency",
    }


def _resolve_majority_vote(_field_name: str, groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Majority-vote: pick the value backed by the most independent sources.

    Prefers the explicit corroboration count when present — reconstructed
    groups carry a single representative URL, so len(source_urls) alone would
    degenerate to a confidence comparison.
    """
    def _votes(g: dict[str, Any]) -> tuple[int, float]:
        votes = int(g.get("corroboration") or 0) or len(g.get("source_urls", set()))
        return (votes, float(g.get("confidence") or 0.0))

    best = max(groups, key=_votes)
    all_urls = list({url for g in groups for url in g.get("source_urls", set())})
    return {
        "value": _display_text(best["value"]),
        "source_urls": all_urls,
        "confidence": float(best.get("confidence") or 0.0),
        "all_values": [
            {"value": _display_text(g["value"]), "source_url": _best_url(g["source_urls"]), "context": None}
            for g in groups
        ],
        "conflict_type": "majority_vote",
        "strategy": "majority_vote",
    }


def _best_url(source_urls: set[str] | list[str]) -> str | None:
    urls = list(source_urls)
    return urls[0] if urls else None


def adjudicator_node(state: AgentState) -> AgentState:
    """Resolve every conflict in state into state["adjudicated"].

    Resolution order per conflict:
      1. Values equivalent (numeric-normalized) → auto-resolve (no LLM).
      2. Field-type strategy (range/union/recency/majority_vote) → deterministic merge (no LLM).
         Runs BEFORE the confidence-gap check so merge-type fields never discard
         legitimate values just because one source scored higher.
      3. Confidence gap > threshold (single-truth debate fields only) → auto-resolve (no LLM).
      4. Pre-flight complementary classifier → if complementary, create MERGE entry (1 LLM call).
      5. Adversarial debate (5-step, 3-5 LLM calls) → winner A/B/FLAG/MERGE.
    """

    run_id = state.get("run_id") or ""
    program_domain = str(state.get("domain") or "")
    program_name = str(state.get("program_name") or "")
    brand = str(state.get("brand") or "")
    raw_conflicts = [item for item in state.get("conflicts") or [] if isinstance(item, dict) and "claim_a" in item]
    if not raw_conflicts:
        raw_conflicts = detect_conflicts_from_packets(
            state.get("normalized_packets", []),
            state.get("raw_documents", []),
            program_domain=program_domain,
            program_name=program_name,
            brand=brand,
        )

    adjudicated: list[dict[str, Any]] = []
    conflict_records: list[dict[str, Any]] = []
    human_review_items: list[dict[str, Any]] = list(state.get("human_review_queue") or [])
    needs_debate: list[dict[str, Any]] = []
    debate_record_indices: list[int] = []

    for conflict in raw_conflicts:
        confidence_a = float(conflict["claim_a"].get("confidence") or 0.0)
        confidence_b = float(conflict["claim_b"].get("confidence") or 0.0)
        score_gap = abs(confidence_a - confidence_b)
        values_identical = _values_equivalent(conflict["claim_a"].get("value"), conflict["claim_b"].get("value"))
        strategy = _classify_field_strategy(conflict["field_name"])
        source_claims = conflict.get("all_claims") or [conflict["claim_a"], conflict["claim_b"]]

        all_values_both = [
            {"value": _display_text(claim.get("value")), "source_url": claim.get("source_url"), "context": None}
            for claim in source_claims
        ]

        # ── Steps 1 & 3: equivalent values, or decisive confidence gap on a
        # single-truth field. Merge-type fields skip the gap check — a higher
        # confidence doesn't make the other source's value wrong for them.
        if values_identical or (strategy == "debate" and score_gap > AUTO_RESOLVE_SCORE_GAP):
            winner = "A" if confidence_a >= confidence_b else "B"
            claim = conflict["claim_a"] if winner == "A" else conflict["claim_b"]
            adjudicated.append({
                "field_name": conflict["field_name"],
                "field_path": conflict["field_name"],
                "conflict_id": new_id("adjudicated"),
                "winner": winner,
                "value": _display_text(claim["value"]),
                "source_url": claim.get("source_url"),
                "confidence": float(claim.get("confidence") or 0.0),
                "resolution": "auto",
                "resolution_status": "auto_resolved",
                "deciding_factor": "confidence_gap",
                "reasoning": (
                    "Auto-resolved: both sources agree on the same value."
                    if values_identical
                    else f"Score gap {score_gap:.2f} > {AUTO_RESOLVE_SCORE_GAP} auto-resolved without debate."
                ),
                "value_a": _display_text(conflict["claim_a"].get("value")),
                "value_b": _display_text(conflict["claim_b"].get("value")),
                "url_a": conflict["claim_a"].get("source_url"),
                "url_b": conflict["claim_b"].get("source_url"),
                "all_values": all_values_both,
                "conflict_type": "contradictory",
                "rounds": [],
            })
            conflict_records.append({
                "conflict_id": new_id("conflict"),
                "run_id": run_id,
                "field_path": conflict["field_name"],
                "claim_ids": [],
                "score_gap": round(score_gap, 4),
                "resolution_status": "auto_resolved",
                "judge_reason": (
                    "Auto-resolved: both sources agree on the same value."
                    if values_identical
                    else f"Auto-resolved: confidence gap {score_gap:.2f} exceeded threshold."
                ),
                "value_a": _display_text(conflict["claim_a"].get("value")),
                "value_b": _display_text(conflict["claim_b"].get("value")),
                "url_a": conflict["claim_a"].get("source_url"),
                "url_b": conflict["claim_b"].get("source_url"),
            })
            continue

        # ── Step 2: field-type strategy (deterministic, no LLM) ─────────────
        if strategy != "debate":
            conflict_records.append({
                "conflict_id": new_id("conflict"),
                "run_id": run_id,
                "field_path": conflict["field_name"],
                "claim_ids": [],
                "score_gap": round(score_gap, 4),
                "resolution_status": "auto_resolved",
                "judge_reason": f"Field-type strategy '{strategy}' applied.",
                "value_a": _display_text(conflict["claim_a"].get("value")),
                "value_b": _display_text(conflict["claim_b"].get("value")),
                "url_a": conflict["claim_a"].get("source_url"),
                "url_b": conflict["claim_b"].get("source_url"),
            })
            # Reconstruct minimal group dicts (from ALL distinct value groups,
            # not just the top two) so strategy functions work
            groups_for_strategy = [
                {
                    "value": claim["value"],
                    "source_urls": {claim.get("source_url") or ""},
                    "confidence": float(claim.get("confidence") or 0.0),
                    "corroboration": int(claim.get("corroboration") or 1),
                }
                for claim in source_claims
            ]
            documents_by_url = {doc.url: doc for doc in (state.get("raw_documents") or [])}
            if strategy == "range":
                resolved = _resolve_range(conflict["field_name"], groups_for_strategy)
            elif strategy == "union":
                resolved = _resolve_union(conflict["field_name"], groups_for_strategy)
            elif strategy == "recency":
                resolved = _resolve_recency(conflict["field_name"], groups_for_strategy, documents_by_url)
            else:  # majority_vote
                resolved = _resolve_majority_vote(conflict["field_name"], groups_for_strategy)

            adjudicated.append({
                "field_name": conflict["field_name"],
                "field_path": conflict["field_name"],
                "conflict_id": new_id("adjudicated"),
                "winner": "MERGE",
                "value": resolved["value"],
                "source_url": resolved["source_urls"][0] if resolved["source_urls"] else None,
                "confidence": resolved["confidence"],
                "resolution": "field_type",
                "resolution_status": "field_type_resolved",
                "deciding_factor": "field_type_strategy",
                "strategy": strategy,
                "reasoning": f"Field strategy '{strategy}': values merged without debate.",
                "value_a": _display_text(conflict["claim_a"].get("value")),
                "value_b": _display_text(conflict["claim_b"].get("value")),
                "url_a": conflict["claim_a"].get("source_url"),
                "url_b": conflict["claim_b"].get("source_url"),
                "all_values": resolved["all_values"],
                "conflict_type": resolved["conflict_type"],
                "rounds": [{
                    "round": 1,
                    "phase": "final_decision",
                    "agent": f"Field Strategy ({strategy})",
                    "argument": f"Applied '{strategy}' strategy: {resolved['value']}",
                }],
            })
            continue

        # ── Steps 4 & 5: pre-flight classifier → debate ──────────────────────
        debate_record_indices.append(len(conflict_records))
        needs_debate.append(conflict)
        conflict_records.append({
            "conflict_id": new_id("conflict"),
            "run_id": run_id,
            "field_path": conflict["field_name"],
            "claim_ids": [],
            "score_gap": round(score_gap, 4),
            "resolution_status": "debate_required",
            "judge_reason": "",
            "value_a": _display_text(conflict["claim_a"].get("value")),
            "value_b": _display_text(conflict["claim_b"].get("value")),
            "url_a": conflict["claim_a"].get("source_url"),
            "url_b": conflict["claim_b"].get("source_url"),
        })

    if needs_debate:
        results = asyncio.run(_run_debates_with_classifier(needs_debate))
        for rec_idx, conflict, result in zip(debate_record_indices, needs_debate, results):
            entries = _entries_from_debate(conflict, result)
            adjudicated.extend(entries)
            winner = result.get("winner")
            if winner == "FLAG":
                score_gap_val = conflict_records[rec_idx].get("score_gap", 0.0)
                human_review_items.append(_build_human_review_item(conflict, result, run_id, score_gap_val))
                conflict_records[rec_idx]["resolution_status"] = "manual_review_needed"
                conflict_records[rec_idx]["judge_reason"] = result.get("reasoning") or FLAG_TEXT
            elif winner == "MERGE":
                conflict_records[rec_idx]["resolution_status"] = "auto_resolved"
                conflict_records[rec_idx]["judge_reason"] = result.get("reasoning") or "Complementary values merged."
            else:
                conflict_records[rec_idx]["judge_reason"] = result.get("reasoning") or ""

    # Synthesise extracted_claims from the field_report so the UI can display them.
    extracted_claims = _claims_from_field_report(state.get("field_report"), run_id)

    updated: AgentState = {
        **state,
        "conflicts": conflict_records,
        "adjudicated": adjudicated,
        "extracted_claims": extracted_claims,
        "human_review_queue": human_review_items,
        "updated_at": now_iso(),
    }
    field_report = state.get("field_report")
    if field_report is not None and adjudicated:
        updated["field_report"] = apply_adjudication_to_field_report(field_report, adjudicated)
    return updated


def _build_human_review_item(
    conflict: dict[str, Any], debate_result: dict[str, Any], run_id: str, score_gap: float = 0.0
) -> dict[str, Any]:
    """Build a structured human-review queue entry when the judge returns FLAG."""
    field_path = str(conflict["field_name"])
    claim_a_id = str(conflict["claim_a"].get("claim_id") or "")
    claim_b_id = str(conflict["claim_b"].get("claim_id") or "")
    return {
        "review_id": new_id("review"),
        "run_id": run_id,
        "field_path": field_path,
        "field_name": field_path,
        "reason": debate_result.get("reasoning") or FLAG_TEXT,
        "claim_ids": [cid for cid in [claim_a_id, claim_b_id] if cid],
        "score_gap": round(score_gap, 4),
        "claim_a": conflict["claim_a"],
        "claim_b": conflict["claim_b"],
        "volatility": conflict.get("volatility"),
        "debate_transcript": {
            "argument_a": debate_result.get("argument_a", ""),
            "argument_b": debate_result.get("argument_b", ""),
            "rebuttal_a": debate_result.get("rebuttal_a", ""),
            "rebuttal_b": debate_result.get("rebuttal_b", ""),
        },
        "judge_verdict": {
            "deciding_factor": debate_result.get("deciding_factor"),
            "reasoning": debate_result.get("reasoning"),
            "rebuttal_assessment": debate_result.get("rebuttal_assessment"),
            "hallucination_detected": debate_result.get("hallucination_detected"),
        },
        "final_confidence": debate_result.get("final_confidence"),
        "flagged_at": now_iso(),
    }


async def _run_debates_with_classifier(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run pre-flight complementary classifier then debate for each conflict.

    Complementary conflicts skip the 5-step debate entirely — the classifier
    result is returned directly as a MERGE verdict (1 call vs 3–5 calls).
    """
    import pipeline.adjudication.debate_engine as _de
    _de._GROQ_SEMAPHORE = asyncio.Semaphore(5)
    _de._CLIENT_POOL = None
    _de._POOL_COUNTER = 0

    async def _safe_one(conflict: dict[str, Any]) -> dict[str, Any]:
        field_name = conflict.get("field_name", "")
        claim_a = conflict["claim_a"]
        claim_b = conflict["claim_b"]
        try:
            # Pre-flight: check if values are complementary before running full debate
            classification = await classify_conflict_type(conflict)
            if classification["conflict_type"] == "complementary":
                merged = classification.get("merged_value") or f"{claim_a['value']} / {claim_b['value']}"
                confidence = max(
                    float(claim_a.get("confidence") or 0.0),
                    float(claim_b.get("confidence") or 0.0),
                )
                return {
                    "field_name": field_name,
                    "winner": "MERGE",
                    "winning_value": merged,
                    "deciding_factor": "complementary",
                    "reasoning": "Pre-flight classifier determined values are complementary (valid in different contexts).",
                    "context_a": classification.get("context_a"),
                    "context_b": classification.get("context_b"),
                    "conflict_type": "complementary",
                    "all_values": [
                        {"value": _display_text(claim_a["value"]), "source_url": claim_a.get("source_url"), "context": classification.get("context_a")},
                        {"value": _display_text(claim_b["value"]), "source_url": claim_b.get("source_url"), "context": classification.get("context_b")},
                    ],
                    "rebuttal_assessment": {"A_rebuttal": "weak", "B_rebuttal": "weak"},
                    "hallucination_detected": {"argument_a": False, "argument_b": False, "rebuttal_a": False, "rebuttal_b": False},
                    "argument_a": "", "argument_b": "", "rebuttal_a": "", "rebuttal_b": "",
                    "final_confidence": confidence,
                    "steps_used": 1,
                }
            # Contradictory — run the full debate
            return await run_debate(conflict, use_rebuttal=True)
        except Exception as exc:
            return {
                "field_name": field_name,
                "winner": "FLAG",
                "winning_value": None,
                "deciding_factor": "unresolvable",
                "reasoning": f"Debate engine error: {exc}",
                "conflict_type": "contradictory",
                "all_values": [
                    {"value": _display_text(claim_a.get("value")), "source_url": claim_a.get("source_url"), "context": None},
                    {"value": _display_text(claim_b.get("value")), "source_url": claim_b.get("source_url"), "context": None},
                ],
                "rebuttal_assessment": {"A_rebuttal": "weak", "B_rebuttal": "weak"},
                "hallucination_detected": {"argument_a": False, "argument_b": False, "rebuttal_a": False, "rebuttal_b": False},
                "argument_a": "", "argument_b": "", "rebuttal_a": "", "rebuttal_b": "",
                "final_confidence": FLAG_CONFIDENCE,
                "steps_used": 0,
            }

    return list(await asyncio.gather(*(_safe_one(c) for c in conflicts)))


def _rounds_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert debate engine output into frontend-consumable DebateRound list."""
    rounds = []
    n = 1
    if result.get("argument_a"):
        rounds.append({"round": n, "phase": "opening", "agent": "Advocate A", "argument": result["argument_a"]})
        n += 1
    if result.get("argument_b"):
        rounds.append({"round": n, "phase": "opening_b", "agent": "Advocate B", "argument": result["argument_b"]})
        n += 1
    if result.get("rebuttal_a"):
        rounds.append({"round": n, "phase": "cross", "agent": "Advocate A", "argument": result["rebuttal_a"]})
        n += 1
    if result.get("rebuttal_b"):
        rounds.append({"round": n, "phase": "cross_b", "agent": "Advocate B", "argument": result["rebuttal_b"]})
        n += 1
    deciding = result.get("deciding_factor", "")
    reasoning = result.get("reasoning", "")
    if deciding:
        rounds.append({"round": n, "phase": "evidence", "agent": "Evidence Referee", "argument": f"Deciding factor: {deciding}. {reasoning}"})
        n += 1
    winner = result.get("winner", "FLAG")
    winning_value = result.get("winning_value")
    if winner in ("A", "B") and winning_value:
        rounds.append({"round": n, "phase": "final_decision", "agent": "Judge", "argument": f"Winner: Claim {winner} — accepted value: {winning_value}. {reasoning}"})
    else:
        rounds.append({"round": n, "phase": "final_decision", "agent": "Judge", "argument": f"FLAG: {reasoning or 'Could not resolve — escalated to human review.'}"})
    return rounds


def _entries_from_debate(conflict: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    rounds = _rounds_from_result(result)
    claim_a = conflict["claim_a"]
    claim_b = conflict["claim_b"]
    winner = result["winner"]
    all_values = result.get("all_values") or [
        {"value": _display_text(claim_a.get("value")), "source_url": claim_a.get("source_url"), "context": None},
        {"value": _display_text(claim_b.get("value")), "source_url": claim_b.get("source_url"), "context": None},
    ]
    # The debate only weighs the top two claims; carry any lower-ranked
    # values through so no observed value disappears from the record.
    for extra in (conflict.get("all_claims") or [])[2:]:
        all_values.append({"value": _display_text(extra.get("value")), "source_url": extra.get("source_url"), "context": None})
    conflict_type = result.get("conflict_type", "contradictory")

    if winner == "FLAG":
        flag_confidence = float(result.get("final_confidence") or FLAG_CONFIDENCE)
        return [
            {
                "field_name": conflict["field_name"],
                "field_path": conflict["field_name"],
                "conflict_id": new_id("adjudicated"),
                "winner": "FLAG",
                "value": _display_text(claim["value"]),
                "source_url": claim.get("source_url"),
                "confidence": flag_confidence,
                "resolution": "flag",
                "resolution_status": "manual_review_needed",
                "deciding_factor": result.get("deciding_factor", "unresolvable"),
                "reasoning": result.get("reasoning", ""),
                "flag": FLAG_TEXT,
                "debate": result,
                "rounds": rounds,
                "value_a": str(claim_a.get("value") or ""),
                "value_b": str(claim_b.get("value") or ""),
                "url_a": claim_a.get("source_url"),
                "url_b": claim_b.get("source_url"),
                "all_values": all_values,
                "conflict_type": conflict_type,
            }
            for claim in (claim_a, claim_b)
        ]

    if winner == "MERGE":
        merged_value = result.get("winning_value") or f"{claim_a['value']} / {claim_b['value']}"
        confidence = float(result.get("final_confidence") or max(
            float(claim_a.get("confidence") or 0.0),
            float(claim_b.get("confidence") or 0.0),
        ))
        return [{
            "field_name": conflict["field_name"],
            "field_path": conflict["field_name"],
            "conflict_id": new_id("adjudicated"),
            "winner": "MERGE",
            "value": merged_value,
            "source_url": claim_a.get("source_url"),
            "confidence": confidence,
            "resolution": "merged",
            "resolution_status": "merged",
            "deciding_factor": result.get("deciding_factor", "complementary"),
            "reasoning": result.get("reasoning", ""),
            "debate": result,
            "rounds": rounds,
            "value_a": str(claim_a.get("value") or ""),
            "value_b": str(claim_b.get("value") or ""),
            "url_a": claim_a.get("source_url"),
            "url_b": claim_b.get("source_url"),
            "all_values": all_values,
            "conflict_type": "complementary",
        }]

    claim = claim_a if winner == "A" else claim_b
    return [{
        "field_name": conflict["field_name"],
        "field_path": conflict["field_name"],
        "conflict_id": new_id("adjudicated"),
        "winner": winner,
        "value": result.get("winning_value") or str(claim["value"]),
        "source_url": claim.get("source_url"),
        "confidence": float(result.get("final_confidence") or 0.0),
        "resolution": "debate",
        "resolution_status": "debate_required",
        "deciding_factor": result.get("deciding_factor", ""),
        "reasoning": result.get("reasoning", ""),
        "debate": result,
        "rounds": rounds,
        "value_a": str(claim_a.get("value") or ""),
        "value_b": str(claim_b.get("value") or ""),
        "url_a": claim_a.get("source_url"),
        "url_b": claim_b.get("source_url"),
        "all_values": all_values,
        "conflict_type": conflict_type,
    }]


def detect_conflicts_from_packets(
    packets: list[NormalizedObjectPacket],
    raw_documents: list[RawDocument],
    program_domain: str = "",
    program_name: str = "",
    brand: str = "",
) -> list[dict[str, Any]]:
    """Find fields where two sources disagree and build debate-ready conflicts.

    Groups EXTRACTED values per field path across all packets; when at least
    two distinct values are backed by distinct sources, the two strongest
    value groups become claim_a and claim_b. Every distinct value group is
    carried in all_claims (strongest first) so merge strategies and the final
    all_values record never silently drop a third-ranked value.
    """

    documents_by_url = {document.url: document for document in raw_documents}
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for packet in packets:
        for field_name, field in packet.fields.items():
            # Include EXTRACTED fields and AMBIGUOUS fields that still carry a value.
            # AMBIGUOUS-with-value arises when the normalizer validation flags a suspicious
            # extraction (e.g. a room count in membership_count). Including it here lets the
            # auto-resolve path pick the correct EXTRACTED value from another source
            # (confidence gap > 0.20 is guaranteed when one side is 0.0).
            # AMBIGUOUS fields with value=None carry no evidence and are always skipped.
            if field.value is None or not field.source_url:
                continue
            if field.status not in ("EXTRACTED", "AMBIGUOUS"):
                continue
            # Fold case/trademark noise so "Delta" and "delta™" corroborate the
            # same value group instead of manufacturing a conflict.
            value_key = _normalize_value_text(json.dumps(field.value, sort_keys=True, ensure_ascii=True, default=str))
            group = groups[field_name].setdefault(
                value_key,
                {"value": field.value, "source_urls": set(), "confidence": 0.0},
            )
            group["source_urls"].add(field.source_url)
            # AMBIGUOUS confidence is kept at 0.0 so EXTRACTED values always win auto-resolve.
            if field.status == "EXTRACTED":
                group["confidence"] = max(group["confidence"], field.confidence or 0.0)

    conflicts: list[dict[str, Any]] = []
    for field_name, value_groups in groups.items():
        if len(value_groups) < 2:
            continue
        ranked = sorted(
            value_groups.values(),
            key=lambda group: (len(group["source_urls"]), group["confidence"]),
            reverse=True,
        )
        all_claims = [
            _claim_from_group(group, documents_by_url, program_domain, program_name, brand)
            for group in ranked
        ]
        claim_a, claim_b = all_claims[0], all_claims[1]
        if claim_a["source_url"] == claim_b["source_url"]:
            continue
        conflicts.append(
            {
                "field_name": field_name,
                "volatility": classify_volatility(field_name),
                "claim_a": claim_a,
                "claim_b": claim_b,
                "all_claims": all_claims,
            }
        )
    return conflicts


def classify_volatility(field_name: str) -> str:
    suffix = field_name.split(".")[-1].lower()
    if suffix in HIGH_VOLATILITY_FIELD_NAMES:
        return "HIGH"
    if suffix in LOW_VOLATILITY_FIELD_NAMES:
        return "LOW"
    section = field_name.split(".")[0].lower()
    return "HIGH" if section in HIGH_VOLATILITY_SECTIONS else "LOW"


def apply_adjudication_to_field_report(
    report: FieldReport,
    adjudicated: list[dict[str, Any]],
) -> FieldReport:
    """Reflect adjudication outcomes in the final field report.

    MERGE / complementary resolutions store all simultaneously-valid values in
    all_values instead of rejected_alternatives, because neither was wrong.
    """

    by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in adjudicated:
        by_field[str(entry["field_name"])].append(entry)

    entries = []
    for entry in report.entries:
        resolutions = by_field.get(entry.field_path)
        if not resolutions:
            entries.append(entry)
            continue
        if any(r["resolution"] == "flag" for r in resolutions):
            entries.append(
                entry.model_copy(update={"status": "flagged", "confidence": FLAG_CONFIDENCE})
            )
            continue
        resolution = resolutions[0]
        winner = resolution.get("winner")
        conflict_type = resolution.get("conflict_type", "contradictory")
        all_values = resolution.get("all_values")

        if winner == "MERGE" or conflict_type in ("complementary", "range", "union", "recency", "majority_vote"):
            # Both values are valid — store in all_values, not rejected_alternatives.
            entries.append(
                entry.model_copy(
                    update={
                        "status": "extracted",
                        "value": resolution["value"],
                        "source_urls": (
                            [resolution["source_url"]] if resolution.get("source_url") else entry.source_urls
                        ),
                        "confidence": resolution["confidence"],
                        "all_values": all_values,
                        "conflict_type": conflict_type,
                        "rejected_alternatives": entry.rejected_alternatives or [],
                    }
                )
            )
        else:
            # Contradictory — losing claim goes to rejected_alternatives.
            rej_value = resolution.get("value_b") if winner == "A" else resolution.get("value_a")
            rej_url = resolution.get("url_b") if winner == "A" else resolution.get("url_a")
            rej_reason = resolution.get("reasoning") or resolution.get("deciding_factor") or "adjudicated"
            new_rejected = {
                "value": rej_value,
                "source_urls": [rej_url] if rej_url else [],
                "reason": rej_reason,
            }
            merged_rejected = [new_rejected] + [
                r for r in (entry.rejected_alternatives or [])
                if str(r.get("value", "")) != str(rej_value or "")
            ]
            entries.append(
                entry.model_copy(
                    update={
                        "status": "extracted",
                        "value": resolution["value"],
                        "source_urls": (
                            [resolution["source_url"]] if resolution.get("source_url") else entry.source_urls
                        ),
                        "confidence": resolution["confidence"],
                        "rejected_alternatives": merged_rejected,
                        "all_values": all_values,
                        "conflict_type": conflict_type,
                    }
                )
            )

    return report.model_copy(
        update={
            "entries": entries,
            "extracted_count": sum(1 for item in entries if item.status == "extracted"),
            "ambiguous_count": sum(1 for item in entries if item.status == "ambiguous"),
            "not_found_count": sum(1 for item in entries if item.status == "not_found"),
            "flagged_count": sum(1 for item in entries if item.status == "flagged"),
        }
    )


def _claim_from_group(
    group: dict[str, Any],
    documents_by_url: dict[str, RawDocument],
    program_domain: str = "",
    program_name: str = "",
    brand: str = "",
) -> dict[str, Any]:
    source_url = _best_source_url(group["source_urls"], documents_by_url)
    document = documents_by_url.get(source_url)
    authority = _dampen_authority_for_domain(
        _document_authority(document), source_url, program_domain, program_name, brand
    )
    return {
        "value": _display_text(group["value"]),
        "source_url": source_url,
        "date": _document_date(document),
        "authority": authority,
        "corroboration": len(group["source_urls"]),
        "confidence": round(float(group["confidence"]), 4),
    }


def _best_source_url(source_urls: set[str], documents_by_url: dict[str, RawDocument]) -> str:
    def authority_score(url: str) -> float:
        document = documents_by_url.get(url)
        return document.source_authority or 0.0 if document else 0.0

    return max(sorted(source_urls), key=authority_score)


def _document_date(document: RawDocument | None) -> date:
    if document and document.retrieved_at:
        try:
            return datetime.fromisoformat(document.retrieved_at).date()
        except ValueError:
            pass
    return date.today()


def _document_authority(document: RawDocument | None) -> str:
    if document is None:
        return DEFAULT_AUTHORITY
    source_type = str(document.metadata.get("source_type") or "").strip().lower()
    return SOURCE_TYPE_TO_AUTHORITY.get(source_type, DEFAULT_AUTHORITY)


_FIELD_STATUS_TO_CLAIM_STATUS = {
    "extracted": "supported",
    "ambiguous": "conflicting",
    "not_found": "not_found/manual_review_needed",
    "flagged": "not_found/manual_review_needed",
}


def _field_attr(entry: Any, attr: str, default: Any = None) -> Any:
    """Get an attribute from either a Pydantic model or a plain dict safely."""
    if isinstance(entry, dict):
        return entry.get(attr, default)
    return getattr(entry, attr, default)


def _claims_from_field_report(field_report: Any, run_id: str) -> list[dict[str, Any]]:
    """Convert FieldReport entries into Claim-compatible dicts for the UI."""
    if field_report is None:
        return []
    if isinstance(field_report, dict):
        entries = field_report.get("entries", [])
    else:
        entries = getattr(field_report, "entries", []) or []
    claims = []
    for entry in entries:
        fp = _field_attr(entry, "field_path", "")
        val = _field_attr(entry, "value")
        st = _field_attr(entry, "status", "not_found")
        src_urls = _field_attr(entry, "source_urls") or []
        snippet = _field_attr(entry, "source_snippet")
        conf = _field_attr(entry, "confidence") or 0.0
        volatility = "high" if classify_volatility(fp) == "HIGH" else "low"
        claims.append({
            "claim_id": new_id("claim"),
            "run_id": run_id,
            "field_path": fp,
            "value_json": val,
            "status": _FIELD_STATUS_TO_CLAIM_STATUS.get(st, "null"),
            "source_url": src_urls[0] if src_urls else None,
            "access_date": None,
            "quote": snippet,
            "confidence": round(float(conf), 4),
            "volatility": volatility,
        })
    return claims
