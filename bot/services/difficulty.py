"""
Heuristics for "this call needs a human".

Triggers:
  - explicit phrases ("speak to a human", "manager", "supervisor")
  - N consecutive tool failures on the same call
  - sentiment flagged by ElevenLabs (when the webhook payload includes one)
"""
from __future__ import annotations

from config import get_settings

settings = get_settings()

# call_id -> consecutive tool-failure count
_failure_counts: dict[str, int] = {}


def record_tool_failure(call_id: str) -> int:
    _failure_counts[call_id] = _failure_counts.get(call_id, 0) + 1
    return _failure_counts[call_id]


def reset_tool_failures(call_id: str) -> None:
    _failure_counts.pop(call_id, None)


def should_transfer_on_failure(call_id: str) -> bool:
    return _failure_counts.get(call_id, 0) >= settings.transfer_after_tool_failures


def transcript_requests_human(text: str | None) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(p in lower for p in settings.transfer_trigger_phrases)
