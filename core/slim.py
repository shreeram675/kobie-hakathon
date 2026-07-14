"""Trim heavy evidence payloads out of polled run responses.

The frontend polls GET /api/run/{run_id} every 2 seconds, but only ever
renders metadata from the evidence fields: scrape status/URL per block,
token counts per chunk, and list lengths. The raw page markdown and chunk
text can push a serialized run state past 10 MB (larger still in compare
mode, which embeds one full state per program), so the poll response keeps
short previews and drops the fields the UI never reads. The untrimmed state
is still persisted and available via GET /api/run/{run_id}?full=true.
"""
from __future__ import annotations

from typing import Any

# Never read by the frontend; reachable via ?full=true or the export endpoint.
_DROPPED_FIELDS = ("raw_documents", "extracted_packets", "normalized_packets", "additional_blocks")

_BLOCK_PREVIEW_CHARS = 400
_CHUNK_PREVIEW_CHARS = 200


def _preview(text: Any, limit: int) -> Any:
    if isinstance(text, str) and len(text) > limit:
        return text[:limit] + f"… [truncated {len(text) - limit} chars — request ?full=true for the rest]"
    return text


def _slim_blocks(blocks: Any) -> Any:
    if not isinstance(blocks, list):
        return blocks
    return [
        {**b, "content": _preview(b.get("content"), _BLOCK_PREVIEW_CHARS)} if isinstance(b, dict) else b
        for b in blocks
    ]


def _slim_chunks(chunks: Any) -> Any:
    if not isinstance(chunks, list):
        return chunks
    return [
        {**c, "chunk_text": _preview(c.get("chunk_text"), _CHUNK_PREVIEW_CHARS)} if isinstance(c, dict) else c
        for c in chunks
    ]


def slim_run_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a serialized run state with evidence payloads reduced
    to previews. Recurses into compare-mode sub-states (compare_b and
    comparison_run.program_states). The input dict is not mutated.
    """
    slim = dict(state)

    for key in _DROPPED_FIELDS:
        slim.pop(key, None)

    if "scraped_blocks" in slim:
        slim["scraped_blocks"] = _slim_blocks(slim["scraped_blocks"])
    fc = slim.get("firecrawl_result")
    if isinstance(fc, dict) and "blocks" in fc:
        slim["firecrawl_result"] = {**fc, "blocks": _slim_blocks(fc["blocks"])}

    for key in ("semantic_chunks", "extraction_chunks", "skipped_chunks"):
        if key in slim:
            slim[key] = _slim_chunks(slim[key])

    if isinstance(slim.get("compare_b"), dict):
        slim["compare_b"] = slim_run_state(slim["compare_b"])
    comp_run = slim.get("comparison_run")
    if isinstance(comp_run, dict) and isinstance(comp_run.get("program_states"), list):
        slim["comparison_run"] = {
            **comp_run,
            "program_states": [
                slim_run_state(ps) if isinstance(ps, dict) else ps
                for ps in comp_run["program_states"]
            ],
        }

    return slim
