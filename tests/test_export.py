from core.export import build_export


def _field_report():
    return {
        "generated_at": "2026-01-01T00:00:00Z",
        "extracted_count": 2,
        "ambiguous_count": 0,
        "not_found_count": 0,
        "flagged_count": 0,
        "entries": [
            {
                "field_path": "program_basics.program_name",
                "category": "program_basics",
                "status": "extracted",
                "value": "Delta SkyMiles",
                "source_urls": ["https://delta.com/skymiles"],
                "confidence": 0.99,
                "corroboration_count": 3,
                "conflict_type": None,
                "rejected_alternatives": [],
                "all_values": None,
            },
            {
                "field_path": "earn_mechanics.base_earn_rate",
                "category": "earn_mechanics",
                "status": "extracted",
                "value": "5 miles per $1",
                "source_urls": ["https://delta.com/earn", "https://thepointsguy.com/delta"],
                "confidence": 0.9,
                "corroboration_count": 2,
                "conflict_type": None,
                "rejected_alternatives": [{"value": "4 miles per $1", "source_urls": ["https://old.com"], "reason": "stale"}],
                "all_values": None,
            },
        ],
    }


def test_build_export_single_mode_fields_carry_source_urls():
    response = {
        "run_id": "run_123",
        "mode": "single",
        "status": "done",
        "updated_at": "2026-01-01T00:00:00Z",
        "data_quality": 0.85,
        "program_name": "Delta SkyMiles",
        "brand": "Delta Air Lines",
        "domain": "loyalty",
        "country_or_region": "US",
        "field_report": _field_report(),
        "final_brief": {"brief_text": "Delta SkyMiles overview.", "word_count": 3, "cited_claim_ids": []},
    }

    export = build_export(response)

    assert export["schema_version"] == "1.0"
    assert export["run_id"] == "run_123"
    assert export["mode"] == "single"

    fields = export["program"]["fields"]
    assert fields["program_basics.program_name"]["value"] == "Delta SkyMiles"
    assert fields["program_basics.program_name"]["source_urls"] == ["https://delta.com/skymiles"]
    assert fields["program_basics.program_name"]["confidence"] == 0.99

    earn = fields["earn_mechanics.base_earn_rate"]
    assert earn["source_urls"] == ["https://delta.com/earn", "https://thepointsguy.com/delta"]
    assert earn["rejected_alternatives"][0]["value"] == "4 miles per $1"

    brief = export["program"]["brief"]
    assert brief["text"] == "Delta SkyMiles overview."
    # Falls back to union of field source_urls since cited_claim_ids is empty.
    assert set(brief["source_urls"]) == {
        "https://delta.com/skymiles",
        "https://delta.com/earn",
        "https://thepointsguy.com/delta",
    }


def test_build_export_missing_field_report_and_brief():
    response = {"run_id": "run_456", "mode": "single", "status": "running"}
    export = build_export(response)
    assert export["program"]["fields"] == {}
    assert export["program"]["brief"] is None


def test_build_export_compare_mode_includes_both_programs_and_comparison():
    response = {
        "run_id": "run_789",
        "mode": "compare",
        "status": "done",
        "updated_at": "2026-01-01T00:00:00Z",
        "data_quality": 0.8,
        "program_name": "Delta SkyMiles",
        "field_report": _field_report(),
        "final_brief": None,
        "compare_b": {
            "program_name": "United MileagePlus",
            "field_report": {
                "entries": [
                    {
                        "field_path": "program_basics.program_name",
                        "category": "program_basics",
                        "status": "extracted",
                        "value": "United MileagePlus",
                        "source_urls": ["https://united.com/mileageplus"],
                        "confidence": 0.97,
                    }
                ]
            },
            "final_brief": None,
        },
        "comparison_brief": {
            "programs": ["Delta SkyMiles", "United MileagePlus"],
            "overall_winner": "Delta SkyMiles",
            "executive_summary": "Delta edges out United on redemption value.",
            "category_verdicts": [
                {
                    "category": "earn_mechanics",
                    "label": "Earning",
                    "winner": "Delta SkyMiles",
                    "insight": "Delta earns faster on flights.",
                    "source_urls": ["https://delta.com/earn"],
                }
            ],
            "key_differentiators": [
                {
                    "topic": "Redemption value",
                    "insight": "Delta miles are worth more on average.",
                    "advantage": "Delta SkyMiles",
                    "source_urls": ["https://thepointsguy.com/delta"],
                    "rejected_note": None,
                }
            ],
            "strategic_profiles": [],
            "differentiation_themes": [],
            "personas": [],
        },
    }

    export = build_export(response)

    assert export["mode"] == "compare"
    assert len(export["programs"]) == 2
    names = {p["program_name"] for p in export["programs"]}
    assert names == {"Delta SkyMiles", "United MileagePlus"}

    comparison = export["comparison"]
    assert comparison["overall_winner"] == "Delta SkyMiles"
    assert comparison["category_verdicts"][0]["source_urls"] == ["https://delta.com/earn"]
    assert comparison["key_differentiators"][0]["source_urls"] == ["https://thepointsguy.com/delta"]
