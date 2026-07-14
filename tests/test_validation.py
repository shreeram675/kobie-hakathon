from pipeline.stages.validation import validate_conversation, validate_input


class FakeChatClient:
    def __init__(self, response):
        self.response = response

    def complete_json(self, messages):
        self.messages = messages
        return self.response


def test_llm_resolved_output_builds_identity():
    result = validate_input(
        "Air India",
        chat_client=FakeChatClient(
            {
                "status": "resolved",
                "program_name": "Air India Maharaja Club",
                "brand": "Air India",
                "domain": "Airline",
                "country_or_region": "India",
                "confidence": 0.95,
            }
        ),
        corroborator=lambda name: True,
    )

    assert result.status == "resolved"
    assert result.identity is not None
    assert result.identity.program_name == "Air India Maharaja Club"
    assert result.identity.domain == "Airline"
    assert result.confidence == 0.95


def test_low_confidence_llm_output_asks_clarification():
    result = validate_input(
        "Marriott",
        chat_client=FakeChatClient(
            {
                "status": "needs_clarification",
                "confidence": 0.72,
                "possible_matches": [
                    {
                        "program_name": "Marriott Bonvoy",
                        "brand": "Marriott",
                        "domain": "Hotel",
                    }
                ],
                "follow_up_questions": [
                    "Are you referring to Marriott Bonvoy, Marriott hotel brand information, or something else?"
                ],
            }
        ),
    )

    assert result.status == "needs_clarification"
    assert result.possible_matches[0].program_name == "Marriott Bonvoy"
    assert len(result.follow_up_questions) == 1


def test_empty_input_rejected_before_llm_call():
    result = validate_input("   ", chat_client=FakeChatClient({}))

    assert result.status == "rejected"
    assert result.confidence == 0


def test_single_possible_match_resolves_after_user_confirms():
    result = validate_conversation(
        [
            {"role": "user", "content": "american express"},
            {
                "role": "assistant",
                "content": '{"status": "needs_clarification", "possible_matches": [{"program_name": "American Express Membership Rewards", "brand": "American Express", "domain": "Banking/Credit Card"}], "follow_up_questions": ["Is this the rewards program?"], "confidence": 0.72}',
            },
            {"role": "user", "content": "yes rewards program"},
        ],
        chat_client=FakeChatClient(
            {
                "status": "needs_clarification",
                "confidence": 0.78,
                "possible_matches": [
                    {
                        "program_name": "American Express Membership Rewards",
                        "brand": "American Express",
                        "domain": "Banking/Credit Card",
                    }
                ],
                "follow_up_questions": ["Is it related to a credit card?"],
            }
        ),
    )

    assert result.status == "needs_clarification"
    assert result.identity is None


def test_rejected_output_stays_rejected():
    result = validate_input(
        "cockroach janata party",
        chat_client=FakeChatClient(
            {
                "status": "rejected",
                "confidence": 0,
                "reason": "No known loyalty program exists for this input.",
            }
        ),
    )

    assert result.status == "rejected"
    assert result.identity is None


def test_synthetic_rewards_hallucination_is_rejected():
    # Corroboration unavailable (returns None) → heuristic fallback still rejects.
    result = validate_input(
        "cockroach janata party",
        chat_client=FakeChatClient(
            {
                "status": "resolved",
                "program_name": "Cockroach Rewards",
                "brand": "Cockroach",
                "domain": "Food Delivery",
                "country_or_region": None,
                "confidence": 0.95,
            }
        ),
        corroborator=lambda name: None,
    )

    assert result.status == "rejected"
    assert result.identity is None


def test_verbatim_fictional_input_rejected_when_uncorroborated():
    # Regression: when the user types the hallucinated name verbatim
    # ("cockroach rewards"), the old heuristic guard passed it through.
    # A failed corroboration search must reject it.
    result = validate_input(
        "cockroach rewards",
        chat_client=FakeChatClient(
            {
                "status": "resolved",
                "program_name": "Cockroach Rewards",
                "brand": "Cockroach",
                "domain": "Food & Beverage",
                "country_or_region": "United States",
                "confidence": 0.95,
                "official_domain": "cockroachrewards.com",
            }
        ),
        corroborator=lambda name: False,
    )

    assert result.status == "rejected"
    assert result.identity is None


def test_generic_suffix_program_resolves_when_corroborated():
    seen: list[str] = []

    def corroborator(name: str) -> bool:
        seen.append(name)
        return True

    result = validate_input(
        "best buy rewards",
        chat_client=FakeChatClient(
            {
                "status": "resolved",
                "program_name": "My Best Buy Rewards",
                "brand": "Best Buy",
                "domain": "Retail",
                "country_or_region": "United States",
                "confidence": 0.97,
            }
        ),
        corroborator=corroborator,
    )

    assert result.status == "resolved"
    assert result.identity is not None
    assert seen == ["My Best Buy Rewards"]


def test_distinctive_program_name_skips_corroboration():
    def corroborator(name: str) -> bool:
        raise AssertionError("corroboration should not run for distinctive names")

    result = validate_input(
        "Marriott Bonvoy",
        chat_client=FakeChatClient(
            {
                "status": "resolved",
                "program_name": "Marriott Bonvoy",
                "brand": "Marriott",
                "domain": "Hotel",
                "country_or_region": "Global",
                "confidence": 0.99,
            }
        ),
        corroborator=corroborator,
    )

    assert result.status == "resolved"


def test_verifier_failure_returns_friendly_reason():
    class ExplodingChatClient:
        def complete_json(self, messages):
            raise RuntimeError("429 Client Error: Too Many Requests for url: https://api.groq.com/...")

    result = validate_input("Marriott Bonvoy", chat_client=ExplodingChatClient())

    assert result.status == "needs_clarification"
    assert "429" not in (result.reason or "")
    assert "temporarily unavailable" in (result.reason or "")


def test_synthetic_possible_match_is_filtered_and_rejected_for_fake_input():
    result = validate_input(
        "cockroach janata party",
        chat_client=FakeChatClient(
            {
                "status": "needs_clarification",
                "confidence": 0.70,
                "possible_matches": [
                    {
                        "program_name": "Cockroach Rewards",
                        "brand": "Cockroach",
                        "domain": "Food Delivery",
                    }
                ],
                "follow_up_questions": ["Is this related to a food delivery service?"],
            }
        ),
    )

    assert result.status == "rejected"
    assert result.possible_matches == []
