"""Tests for core.slim — the polled-response payload reducer."""

from core.slim import slim_run_state


def _sample_state() -> dict:
    long_content = "A" * 5000
    long_chunk = "B" * 3000
    return {
        "run_id": "run_1",
        "status": "running",
        "program_name": "Delta SkyMiles",
        "scraped_blocks": [
            {"url": "https://delta.com", "scrape_status": "success", "content": long_content},
            {"url": "https://fail.example", "scrape_status": "failed", "content": None},
        ],
        "firecrawl_result": {
            "total_urls": 2,
            "successful_scrapes": 1,
            "blocks": [{"url": "https://delta.com", "scrape_status": "success", "content": long_content}],
        },
        "semantic_chunks": [{"chunk_id": "c1", "token_count": 512, "chunk_text": long_chunk}],
        "extraction_chunks": [{"chunk_id": "c1", "token_count": 512, "chunk_text": long_chunk}],
        "skipped_chunks": [],
        "raw_documents": [{"url": "https://delta.com", "content": long_content}],
        "extracted_packets": [{"object_type": "earn_mechanics"}],
        "normalized_packets": [{"object_type": "earn_mechanics"}],
        "additional_blocks": [{"url": "https://wikipedia.org", "content": long_content}],
        "field_report": {"entries": [{"field_path": "program_basics.program_name"}]},
        "final_brief": {"brief_text": "short brief"},
    }


def test_drops_fields_the_ui_never_reads():
    slim = slim_run_state(_sample_state())
    for key in ("raw_documents", "extracted_packets", "normalized_packets", "additional_blocks"):
        assert key not in slim


def test_truncates_block_content_but_keeps_metadata_and_truthiness():
    slim = slim_run_state(_sample_state())
    ok, failed = slim["scraped_blocks"]
    assert len(ok["content"]) < 5000
    assert ok["content"]  # success counting relies on truthiness
    assert ok["scrape_status"] == "success"
    assert failed["content"] is None  # None must stay None, not become a string
    fc_block = slim["firecrawl_result"]["blocks"][0]
    assert len(fc_block["content"]) < 5000


def test_truncates_chunk_text_but_keeps_token_count():
    slim = slim_run_state(_sample_state())
    chunk = slim["semantic_chunks"][0]
    assert chunk["token_count"] == 512
    assert len(chunk["chunk_text"]) < 3000


def test_short_values_and_analysis_outputs_pass_through_unchanged():
    state = _sample_state()
    slim = slim_run_state(state)
    assert slim["field_report"] == state["field_report"]
    assert slim["final_brief"] == state["final_brief"]
    assert slim["status"] == "running"
    # input is not mutated
    assert len(state["scraped_blocks"][0]["content"]) == 5000
    assert "raw_documents" in state


def test_recurses_into_compare_mode_substates():
    inner = _sample_state()
    state = {
        "run_id": "run_2",
        "mode": "compare",
        "compare_b": _sample_state(),
        "comparison_run": {
            "programs": ["A", "B"],
            "program_states": [inner, None],
        },
    }
    slim = slim_run_state(state)
    assert "raw_documents" not in slim["compare_b"]
    slim_inner = slim["comparison_run"]["program_states"][0]
    assert "raw_documents" not in slim_inner
    assert len(slim_inner["scraped_blocks"][0]["content"]) < 5000
    assert slim["comparison_run"]["program_states"][1] is None
