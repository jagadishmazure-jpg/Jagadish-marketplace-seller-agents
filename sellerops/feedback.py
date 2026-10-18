"""User feedback capture with PII scrubbing before storage.

Thumbs up/down plus free-text corrections. Free text is scrubbed for
emails, phone numbers, and SSN-like patterns BEFORE it reaches the audit
log — storing raw PII was a real gap caught in review on sibling repos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# Anchored: the old pattern swallowed the preceding space and matched inside
# order IDs and longer numbers ("ORD-20[phone]").
_PHONE = re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD = re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b")


class FeedbackError(ValueError):
    pass


def scrub_pii(text: str) -> tuple[str, int]:
    """Redact PII patterns. Returns (scrubbed, redaction_count)."""
    count = 0

    def _sub(rx: re.Pattern, repl: str, s: str) -> str:
        nonlocal count
        s, n = rx.subn(repl, s)
        count += n
        return s

    out = text
    out = _sub(_EMAIL, "[email]", out)
    out = _sub(_PHONE, "[phone]", out)
    out = _sub(_SSN, "[ssn]", out)
    out = _sub(_CARD, "[card]", out)
    return out, count


@dataclass
class Feedback:
    feedback_id: str
    session_id: str
    turn_id: str
    rating: str              # "up" | "down"
    correction: str = ""     # scrubbed
    redactions: int = 0


class FeedbackStore:
    def __init__(self, audit) -> None:
        self._audit = audit
        self._items: list[Feedback] = []
        self._seq = 0

    def capture(self, session_id: str, turn_id: str, rating: str,
                correction: str = "") -> Feedback:
        if rating not in ("up", "down"):
            raise FeedbackError(f"rating must be 'up' or 'down', got {rating!r}")
        if not session_id.strip() or not turn_id.strip():
            raise FeedbackError("session_id and turn_id are required")
        scrubbed, n = scrub_pii(correction or "")
        if rating == "down" and not scrubbed.strip():
            raise FeedbackError("thumbs-down requires a non-empty correction")
        self._seq += 1
        fb = Feedback(f"FB-{self._seq:04d}", session_id, turn_id,
                      rating, scrubbed, n)
        self._items.append(fb)
        self._audit.record("user", "feedback",
                           f"{fb.feedback_id} {rating} redactions={n}")
        return fb

    def list(self) -> list[Feedback]:
        return list(self._items)
