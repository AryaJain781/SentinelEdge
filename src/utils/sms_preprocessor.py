"""SMS text cleaner and metadata extractor (offline, pure Python).

Two steps:

1. ``clean_sms`` replaces URLs, phone numbers and money amounts with fixed
   tokens (``<URL>``, ``<PHONE>``, ``<CURRENCY>``) and normalises whitespace.
   The tokens stop the model memorising specific numbers or links.
2. ``extract_sms_metadata`` counts scam-related signals in the raw text:
   urgency words, exclamation marks, upper-case ratio and financial triggers.
"""

from __future__ import annotations

import re

URL_TOKEN = "<URL>"
PHONE_TOKEN = "<PHONE>"
CURRENCY_TOKEN = "<CURRENCY>"

# Links: explicit schemes, "www." prefixes, and bare domains such as bit.ly/x.
_URL = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+\.(?:com|net|org|info|xyz|top|tk|ly|co|in|me)"
    r"(?:/\S*)?\b",
    re.IGNORECASE,
)
# Phone numbers: optional +, then 9 to 15 digits with spaces or dashes between.
_PHONE = re.compile(r"(?<!\w)\+?\d(?:[\s-]?\d){8,14}(?!\w)")
# Money: a currency symbol or code followed by an amount, or an amount then a code.
_CURRENCY = re.compile(
    r"(?:[£$€₹]\s?\d[\d,.]*)|(?:\d[\d,.]*\s?(?:rs|inr|usd|gbp|eur|rupees?|dollars?|pounds?))",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")

URGENCY_WORDS: tuple[str, ...] = (
    "urgent",
    "immediately",
    "now",
    "today",
    "asap",
    "suspend",
    "suspended",
    "expire",
    "expires",
    "expired",
    "final",
    "last warning",
    "within 24 hours",
    "act now",
    "limited time",
    "blocked",
    "terminate",
)

FINANCIAL_WORDS: tuple[str, ...] = (
    "bank",
    "account",
    "otp",
    "pin",
    "refund",
    "prize",
    "won",
    "cash",
    "loan",
    "credit",
    "debit",
    "payment",
    "transfer",
    "reward",
    "fee",
    "fine",
    "upi",
)

SMS_METADATA_NAMES: tuple[str, ...] = (
    "urgency_count",
    "exclamation_count",
    "uppercase_ratio",
    "financial_count",
    "has_url",
    "has_phone",
    "has_currency",
    "length_chars",
)


def clean_sms(text: str) -> str:
    """Replace URLs, phone numbers and money with tokens, lower-case, tidy spaces.

    URLs are replaced first, so digits inside a link are not mistaken for a
    phone number.
    """
    cleaned = text.lower()
    cleaned = _URL.sub(f" {URL_TOKEN} ", cleaned)
    cleaned = _CURRENCY.sub(f" {CURRENCY_TOKEN} ", cleaned)
    cleaned = _PHONE.sub(f" {PHONE_TOKEN} ", cleaned)
    return _WHITESPACE.sub(" ", cleaned).strip()


def _count_phrases(text_lower: str, phrases: tuple[str, ...]) -> int:
    """Count whole-word occurrences of each phrase."""
    total = 0
    for phrase in phrases:
        total += len(re.findall(rf"(?<!\w){re.escape(phrase)}(?!\w)", text_lower))
    return total


def extract_sms_metadata(text: str) -> dict[str, float]:
    """Return the scam-signal metadata for one raw SMS (before cleaning)."""
    lowered = text.lower()
    letters = [ch for ch in text if ch.isalpha()]
    uppercase = sum(ch.isupper() for ch in letters)
    uppercase_ratio = uppercase / len(letters) if letters else 0.0
    return {
        "urgency_count": float(_count_phrases(lowered, URGENCY_WORDS)),
        "exclamation_count": float(text.count("!")),
        "uppercase_ratio": float(uppercase_ratio),
        "financial_count": float(_count_phrases(lowered, FINANCIAL_WORDS)),
        "has_url": float(bool(_URL.search(text))),
        "has_phone": float(bool(_PHONE.search(text))),
        "has_currency": float(bool(_CURRENCY.search(text))),
        "length_chars": float(len(text)),
    }
