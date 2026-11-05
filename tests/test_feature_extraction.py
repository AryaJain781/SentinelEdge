"""Tests for URL, SMS and network feature extraction and entropy maths."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.utils.network_preprocessor import (
    ATTACK_CATEGORY,
    FEATURE_COLUMNS,
    UnknownAttackError,
    parse_nsl_kdd,
)
from src.utils.sms_preprocessor import (
    CURRENCY_TOKEN,
    PHONE_TOKEN,
    URL_TOKEN,
    clean_sms,
    extract_sms_metadata,
)
from src.utils.url_features import (
    FEATURE_NAMES,
    extract_url_features,
    shannon_entropy,
)

# ------------------------------------------------------------------ entropy


def test_entropy_of_single_repeated_character_is_zero() -> None:
    assert shannon_entropy("aaaa") == 0.0


def test_entropy_of_two_equal_characters_is_one_bit() -> None:
    assert shannon_entropy("ab") == pytest.approx(1.0)


def test_entropy_of_four_distinct_characters_is_two_bits() -> None:
    assert shannon_entropy("abcd") == pytest.approx(2.0)


def test_entropy_of_empty_string_is_zero() -> None:
    assert shannon_entropy("") == 0.0


def test_random_looking_domain_has_higher_entropy_than_brand_name() -> None:
    assert shannon_entropy("x7kq2pl9mz") > shannon_entropy("google")


# -------------------------------------------------------------------- URLs


def test_url_returns_exactly_18_features_in_order() -> None:
    features = extract_url_features("https://www.example.com/a/b?x=1&y=2")
    assert len(FEATURE_NAMES) == 18
    assert list(features) == list(FEATURE_NAMES)


def test_raw_ip_host_is_flagged() -> None:
    assert extract_url_features("http://192.168.0.1/login")["is_ip_host"] == 1.0


def test_normal_domain_is_not_an_ip() -> None:
    assert extract_url_features("https://example.com")["is_ip_host"] == 0.0


def test_suspicious_tld_is_flagged() -> None:
    assert (
        extract_url_features("http://paypal-secure.xyz/login")["suspicious_tld"] == 1.0
    )
    assert extract_url_features("https://www.paypal.com")["suspicious_tld"] == 0.0


def test_brand_impersonation_is_counted_only_when_name_differs() -> None:
    impostor = extract_url_features("http://paypal-secure.xyz/login")
    real = extract_url_features("https://www.paypal.com")
    assert impostor["brand_keyword_hits"] == 1.0
    assert real["brand_keyword_hits"] == 0.0


def test_counts_of_dots_hyphens_slashes_and_digits() -> None:
    features = extract_url_features("http://a-b.c1.com/x/y2")
    assert features["dot_count"] == 2.0
    assert features["hyphen_count"] == 1.0
    assert features["slash_count"] == 4.0
    assert features["digit_count"] == 2.0


def test_length_features_match_string_lengths() -> None:
    url = "https://sub.example.com/some/path"
    features = extract_url_features(url)
    assert features["url_length"] == float(len(url))
    assert features["hostname_length"] == float(len("sub.example.com"))
    assert features["path_length"] == float(len("/some/path"))


def test_subdomain_count_ignores_registrable_domain() -> None:
    assert extract_url_features("https://www.paypal.com")["subdomain_count"] == 1.0
    assert extract_url_features("https://paypal.com")["subdomain_count"] == 0.0


def test_login_keywords_are_counted() -> None:
    features = extract_url_features("http://x.com/login-verify")
    assert features["login_keyword_count"] == 2.0


def test_at_symbol_and_underscore_and_query_params() -> None:
    features = extract_url_features("http://bank.com@evil.com/a_b?x=1&y=2")
    assert features["has_at_symbol"] == 1.0
    assert features["underscore_count"] == 1.0
    assert features["query_param_count"] == 2.0


def test_https_and_port_flags() -> None:
    assert extract_url_features("https://a.com")["uses_https"] == 1.0
    assert extract_url_features("http://a.com")["uses_https"] == 0.0
    assert extract_url_features("http://a.com:8080/")["has_port"] == 1.0


def test_malformed_port_does_not_raise() -> None:
    features = extract_url_features("http://example.com:abc/")
    assert features["has_port"] == 0.0


def test_url_without_scheme_is_tolerated() -> None:
    features = extract_url_features("paypal.com/login")
    assert features["hostname_length"] == float(len("paypal.com"))


def test_entropy_feature_uses_hostname_only() -> None:
    features = extract_url_features("http://aaaa.com/zzzzqqqq")
    assert features["domain_entropy"] == pytest.approx(shannon_entropy("aaaa.com"))


def test_all_feature_values_are_finite_numbers() -> None:
    for url in ["", "http://", "https://a.b.c.d.e.f/g?h=i#j", "ftp://1.2.3.4:99/x"]:
        values = extract_url_features(url or "x")
        assert all(math.isfinite(v) for v in values.values())


# --------------------------------------------------------------------- SMS


def test_clean_sms_replaces_url_phone_and_currency_tokens() -> None:
    text = "Call +44 7700 900123 now, visit http://bit.ly/x1 pay £500"
    cleaned = clean_sms(text)
    assert URL_TOKEN in cleaned
    assert PHONE_TOKEN in cleaned
    assert CURRENCY_TOKEN in cleaned
    assert "bit.ly" not in cleaned
    assert "900123" not in cleaned


def test_clean_sms_handles_bare_domain() -> None:
    assert URL_TOKEN in clean_sms("Claim at prize-win.xyz/now today")


def test_clean_sms_lowercases_and_collapses_whitespace() -> None:
    assert clean_sms("HELLO   There\n\nFriend") == "hello there friend"


def test_clean_sms_keeps_short_numbers_such_as_otp_length_codes() -> None:
    # Six-digit OTPs are below the phone-number length, so they are not tokenised.
    assert PHONE_TOKEN not in clean_sms("Your code is 123456")


def test_sms_metadata_counts_urgency_and_exclamations() -> None:
    meta = extract_sms_metadata("URGENT!!! Your account is suspended. Click now")
    assert meta["urgency_count"] == 3.0
    assert meta["exclamation_count"] == 3.0
    assert meta["financial_count"] == 1.0


def test_sms_uppercase_ratio_is_fraction_of_letters() -> None:
    meta = extract_sms_metadata("ABcd")
    assert meta["uppercase_ratio"] == pytest.approx(0.5)


def test_sms_uppercase_ratio_is_zero_without_letters() -> None:
    assert extract_sms_metadata("1234 !!")["uppercase_ratio"] == 0.0


def test_sms_flags_url_phone_and_currency() -> None:
    meta = extract_sms_metadata("Win £1000 at http://x.com or call 9876543210")
    assert meta["has_url"] == 1.0
    assert meta["has_phone"] == 1.0
    assert meta["has_currency"] == 1.0


# ---------------------------------------------------------------- network


def _record(attack: str, difficulty: int = 20, sep: str = "\t") -> str:
    values = ["0", "tcp", "private", "REJ"] + ["0"] * 37
    return sep.join([*values, attack, str(difficulty)])


def test_nsl_kdd_parser_names_41_features(tmp_path: Path) -> None:
    path = tmp_path / "KDD.txt"
    path.write_text(_record("neptune") + "\n", encoding="utf-8")
    frame = parse_nsl_kdd(path)
    for column in FEATURE_COLUMNS:
        assert column in frame.columns
    assert len(FEATURE_COLUMNS) == 41


def test_nsl_kdd_binary_label_and_category(tmp_path: Path) -> None:
    path = tmp_path / "KDD.txt"
    path.write_text(
        "\n".join([_record("normal"), _record("neptune"), _record("nmap")]) + "\n",
        encoding="utf-8",
    )
    frame = parse_nsl_kdd(path)
    assert frame["label"].tolist() == [0, 1, 1]
    assert frame["attack_category"].tolist() == ["Normal", "DoS", "Probe"]


def test_nsl_kdd_accepts_comma_separated_copies(tmp_path: Path) -> None:
    path = tmp_path / "KDD.csv"
    path.write_text(_record("normal", sep=",") + "\n", encoding="utf-8")
    frame = parse_nsl_kdd(path)
    assert frame.shape[1] == 41 + 3
    assert frame["label"].tolist() == [0]


def test_nsl_kdd_unknown_attack_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "KDD.txt"
    path.write_text(_record("mystery_attack") + "\n", encoding="utf-8")
    with pytest.raises(UnknownAttackError):
        parse_nsl_kdd(path)


def test_nsl_kdd_wrong_column_count_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "KDD.txt"
    path.write_text("1\t2\t3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_nsl_kdd(path)


def test_every_attack_has_one_of_five_categories() -> None:
    assert set(ATTACK_CATEGORY.values()) == {"Normal", "DoS", "Probe", "R2L", "U2R"}
