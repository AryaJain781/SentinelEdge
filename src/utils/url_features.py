"""Offline static feature extractor for URLs (18 numeric clues).

Every feature is computed from the URL string alone. Nothing is fetched, so
the extractor is safe to run on the phone (see ADR-0007). The features are
simple, explainable clues, not a complete phishing classifier.

Typical use::

    from src.utils.url_features import extract_url_features
    features = extract_url_features("http://paypa1-verify.xyz/login")
"""

from __future__ import annotations

import math
import re
from collections import Counter
from urllib.parse import SplitResult, urlsplit

FEATURE_NAMES: tuple[str, ...] = (
    "url_length",
    "hostname_length",
    "path_length",
    "dot_count",
    "hyphen_count",
    "slash_count",
    "digit_count",
    "is_ip_host",
    "domain_entropy",
    "suspicious_tld",
    "brand_keyword_hits",
    "subdomain_count",
    "has_at_symbol",
    "underscore_count",
    "query_param_count",
    "uses_https",
    "has_port",
    "login_keyword_count",
)

# Top-level domains that are cheap or free and often abused. A clue, not proof.
SUSPICIOUS_TLDS: frozenset[str] = frozenset(
    {
        "xyz",
        "top",
        "tk",
        "ml",
        "ga",
        "cf",
        "gq",
        "zip",
        "click",
        "country",
        "kim",
        "work",
    }
)

# Well-known brands that phishing pages often copy.
BRAND_KEYWORDS: tuple[str, ...] = (
    "paypal",
    "apple",
    "microsoft",
    "google",
    "amazon",
    "netflix",
    "facebook",
    "instagram",
    "whatsapp",
    "irs",
    "sbi",
    "hdfc",
    "icici",
)

LOGIN_KEYWORDS: tuple[str, ...] = (
    "login",
    "signin",
    "verify",
    "secure",
    "account",
    "update",
    "confirm",
    "password",
    "banking",
)

_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_IPV6 = re.compile(r"^\[?[0-9a-fA-F:]*:[0-9a-fA-F:]*\]?$")


def shannon_entropy(text: str) -> float:
    """Shannon entropy in bits per character. Empty text gives 0.0."""
    if not text:
        return 0.0
    total = len(text)
    counts = Counter(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def _registrable_name_and_tld(hostname: str) -> tuple[str, str]:
    """Return (second-level name, TLD) using the last two labels.

    This is a simple approximation. It does not know multi-part suffixes such
    as ``co.uk``, which is a known limitation and is recorded in the docs.
    """
    labels = [label for label in hostname.split(".") if label]
    if len(labels) < 2:
        return (labels[0] if labels else "", "")
    return labels[-2], labels[-1]


def extract_url_features(url: str) -> dict[str, float]:
    """Compute the 18 clues for one URL string.

    A missing scheme is tolerated: ``paypal.com/login`` is parsed as if it had
    ``http://``. Returns a dict keyed by ``FEATURE_NAMES``, in that order.
    """
    raw = url.strip()
    candidate = raw if "://" in raw else f"http://{raw}"
    parts = urlsplit(candidate)
    hostname = (parts.hostname or "").lower()
    path = parts.path or ""
    query = parts.query or ""
    name, tld = _registrable_name_and_tld(hostname)
    lowered = raw.lower()

    is_ip = bool(_IPV4.match(hostname) or _IPV6.match(hostname))
    brand_hits = sum(
        1 for brand in BRAND_KEYWORDS if brand in hostname and name != brand
    )
    login_hits = sum(1 for word in LOGIN_KEYWORDS if word in lowered)
    subdomains = max(len([label for label in hostname.split(".") if label]) - 2, 0)
    query_params = len([p for p in query.split("&") if p]) if query else 0

    features: dict[str, float] = {
        "url_length": float(len(raw)),
        "hostname_length": float(len(hostname)),
        "path_length": float(len(path)),
        "dot_count": float(raw.count(".")),
        "hyphen_count": float(raw.count("-")),
        "slash_count": float(raw.count("/")),
        "digit_count": float(sum(ch.isdigit() for ch in raw)),
        "is_ip_host": float(is_ip),
        "domain_entropy": shannon_entropy(hostname),
        "suspicious_tld": float(tld in SUSPICIOUS_TLDS),
        "brand_keyword_hits": float(brand_hits),
        "subdomain_count": float(subdomains),
        "has_at_symbol": float("@" in raw),
        "underscore_count": float(raw.count("_")),
        "query_param_count": float(query_params),
        "uses_https": float(parts.scheme == "https"),
        "has_port": float(_has_valid_port(parts)),
        "login_keyword_count": float(login_hits),
    }
    return {key: features[key] for key in FEATURE_NAMES}


def _has_valid_port(parts: SplitResult) -> bool:
    """True only when the URL names a valid numeric port (malformed ports are False)."""
    try:
        return parts.port is not None
    except ValueError:
        return False
