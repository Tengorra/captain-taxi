"""Unit tests for the difficulty / escalation heuristics."""
from services import difficulty


def test_phrase_match_speak_to_a_human():
    assert difficulty.transcript_requests_human("Can I speak to a human please?")
    assert difficulty.transcript_requests_human("I want a real person")
    assert difficulty.transcript_requests_human("Get me a MANAGER right now")
    assert difficulty.transcript_requests_human("this is ridiculous")


def test_phrase_match_negative_cases():
    assert not difficulty.transcript_requests_human("I want to book a taxi")
    assert not difficulty.transcript_requests_human("")
    assert not difficulty.transcript_requests_human(None)


def test_failure_counter_increments_and_triggers():
    call = "test-call-A"
    difficulty.reset_tool_failures(call)
    assert difficulty.record_tool_failure(call) == 1
    assert not difficulty.should_transfer_on_failure(call)
    assert difficulty.record_tool_failure(call) == 2
    # Default threshold is 2 consecutive failures → should transfer now.
    assert difficulty.should_transfer_on_failure(call)


def test_failure_counter_isolated_per_call():
    difficulty.reset_tool_failures("call-X")
    difficulty.reset_tool_failures("call-Y")
    difficulty.record_tool_failure("call-X")
    difficulty.record_tool_failure("call-X")
    assert difficulty.should_transfer_on_failure("call-X")
    assert not difficulty.should_transfer_on_failure("call-Y")


def test_reset_clears_counter():
    call = "test-call-B"
    difficulty.record_tool_failure(call)
    difficulty.record_tool_failure(call)
    assert difficulty.should_transfer_on_failure(call)
    difficulty.reset_tool_failures(call)
    assert not difficulty.should_transfer_on_failure(call)
