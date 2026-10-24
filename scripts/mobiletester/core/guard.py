"""Flags UI elements whose activation could cost money, contact real people or destroy an account.

This is a safety net, not a guarantee: it only sees English labels and resource ids. The skills
still tell the agent to judge each screen itself.
"""

from __future__ import annotations

import re

RISK_PATTERNS: dict[str, re.Pattern[str]] = {
    "payment": re.compile(
        r"\b(buy|purchase|pay|pay now|checkout|check out|place order|subscribe|subscription|"
        r"start (free )?trial|upgrade|add (credit |debit )?card|payment|donate|tip)\b"
    ),
    "message": re.compile(
        r"\b(send|post|publish|share|reply|tweet|invite|submit review|write a review|rate)\b"
    ),
    "account": re.compile(
        r"\b(delete( account| my account)?|remove account|deactivate|close account|log ?out|sign ?out|"
        r"change password|reset password|erase|wipe|factory reset)\b"
    ),
}

_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
_MAX_ACTION_WORDS = 6


def action_like(text: str) -> bool:
    """Buttons say what they do in a few words; questions and sentences describe something instead."""
    text = text.strip()
    return bool(text) and not text.endswith("?") and len(text.split()) <= _MAX_ACTION_WORDS


def _normalize(text: str) -> str:
    # Resource ids like `btn_buyNow` should match `buy now`.
    return _CAMEL_RE.sub(" ", text).replace("_", " ").replace("-", " ").casefold()


def classify(label: str, resource_id: str = "") -> str | None:
    """Return the risk category of an element, or None when it looks harmless."""
    haystack = f"{_normalize(label)} | {_normalize(resource_id)}"
    for category, pattern in RISK_PATTERNS.items():
        if pattern.search(haystack):
            return category
    return None
