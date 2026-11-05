"""Edge-case tests: empty input, very long messages, malformed URLs, emoji,
non-English text and bad numbers. Every case must either return a valid
answer or raise a clear error. None may crash with an unexplained exception.
"""

from __future__ import annotations

import math
import time

import pytest

from src.detectors.network_detector import NetworkDetector
from src.detectors.sms_detector import MODEL_PATH as SMS_MODEL
from src.detectors.sms_detector import load_sms_detector
from src.detectors.url_detector import MODEL_PATH as URL_MODEL
from src.detectors.url_detector import URLDetector
from src.pipeline.router import RouterError, analyze, detect_input_type
from src.ui.cli import parse_network_record, render
from src.utils.data_loader import PROCESSED_DIR

needs_sms = pytest.mark.skipif(not SMS_MODEL.exists(), reason="SMS model not trained")
needs_url = pytest.mark.skipif(not URL_MODEL.exists(), reason="URL model not trained")

VALID_LABELS = {"ham", "spam"}
SMS_EDGE_TEXTS = {
    "empty": "",
    "spaces_only": "     ",
    "newlines_only": "\n\n\t",
    "emoji": "🎉🎉 You won 🎁 claim now 🔥 http://win.xyz 💰",
    "hindi": "आपका बैंक खाता बंद हो जाएगा। कृपया OTP साझा करें।",
    "spanish": "Su cuenta será suspendida. Envíe su código ahora.",
    "chinese": "您的账户已被冻结，请立即回复验证码。",
    "control_chars": "hello\x00\x01\x07 world",
    "repeated_symbols": "!!!!!!!!!!!!!!!!!!!!??????????",
}


@needs_sms
@pytest.mark.parametrize("name", sorted(SMS_EDGE_TEXTS))
def test_sms_edge_cases_return_a_valid_answer(name: str) -> None:
    detector = load_sms_detector()
    result = detector.predict(SMS_EDGE_TEXTS[name])
    assert result["label"] in VALID_LABELS
    assert 0.0 <= result["confidence"] <= 1.0
    assert math.isfinite(result["confidence"])


@needs_sms
def test_very_long_message_is_handled() -> None:
    """A 12,000-character message must be answered, within a generous time limit."""
    long_text = (
        "Urgent! Your account is suspended, click http://bit.ly/x1 now. "
    ) * 200
    assert len(long_text) > 10_000
    started = time.perf_counter()
    result = load_sms_detector().predict(long_text)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    assert result["label"] in VALID_LABELS
    assert elapsed_ms < 2000, f"long message took {elapsed_ms:.0f} ms"


@needs_sms
def test_extremely_long_message_is_truncated_safely() -> None:
    result = load_sms_detector().predict("a " * 50_000)
    assert result["label"] in VALID_LABELS


@needs_sms
def test_non_string_sms_input_is_rejected_clearly() -> None:
    with pytest.raises(TypeError):
        load_sms_detector().predict(None)  # type: ignore[arg-type]


@needs_sms
def test_router_handles_empty_text_without_crashing() -> None:
    verdict = analyze("")
    assert verdict.status == "ok"
    assert verdict.input_type == "sms"
    assert verdict.is_threat is False


@needs_sms
def test_router_handles_emoji_and_non_english() -> None:
    for text in SMS_EDGE_TEXTS.values():
        verdict = analyze(text)
        assert verdict.status == "ok"


# ------------------------------------------------------------ malformed URLs


@pytest.mark.parametrize(
    "raw",
    [
        "http://",
        "https://",
        "www.",
        "http://[::1",
        "http://exa mple.com",
        "ftp:/bad",
        "http://a.com:99999999/x",
        "http://xn--bad--.com",
    ],
)
def test_malformed_urls_are_never_guessed(raw: str) -> None:
    verdict = analyze(raw)
    assert verdict.status == "unsupported" or verdict.input_type == "sms"
    assert verdict.explanation is None or verdict.is_threat


def test_scheme_only_string_is_treated_as_url() -> None:
    assert detect_input_type("http://") == "url"
    assert detect_input_type("https://") == "url"


def test_url_with_spaces_is_treated_as_text() -> None:
    assert detect_input_type("paypal login now http://x.xyz") == "sms"


@needs_url
def test_url_features_reject_nan_and_inf() -> None:
    detector = URLDetector(_bundle_for("url"))
    sample = _url_sample()
    for bad in (math.nan, math.inf, -math.inf):
        sample[next(iter(sample))] = bad
        with pytest.raises(ValueError):
            detector.predict(sample)


@needs_url
def test_url_features_reject_text_values() -> None:
    detector = URLDetector(_bundle_for("url"))
    sample = _url_sample()
    sample[next(iter(sample))] = "not a number"
    with pytest.raises(ValueError):
        detector.predict(sample)


@needs_url
def test_url_features_missing_are_reported() -> None:
    with pytest.raises(KeyError):
        URLDetector(_bundle_for("url")).predict({})


def _bundle_for(domain: str) -> dict:
    from src.detectors.base import load_bundle

    return load_bundle(URL_MODEL if domain == "url" else SMS_MODEL)


def _url_sample() -> dict[str, float]:
    import pandas as pd

    row = pd.read_csv(PROCESSED_DIR / "url" / "val.csv").iloc[0]
    return {k: float(v) for k, v in row.items() if k not in ("row_id", "label")}


# ------------------------------------------------------------- network input


def test_network_empty_dict_is_rejected() -> None:
    with pytest.raises(RouterError):
        detect_input_type({})


def test_network_dict_with_missing_fields_is_reported() -> None:
    detector = NetworkDetector({"pipeline": None, "threshold": 0.5})
    with pytest.raises(KeyError):
        detector.to_frame({"protocol_type": "tcp"})


def test_network_record_with_nan_is_rejected() -> None:
    import pandas as pd

    from src.utils.network_preprocessor import FEATURE_COLUMNS

    row = pd.read_csv(PROCESSED_DIR / "network" / "val.csv").iloc[0]
    sample = {c: row[c] for c in FEATURE_COLUMNS}
    sample["duration"] = math.nan
    detector = NetworkDetector({"pipeline": None, "threshold": 0.5})
    with pytest.raises(ValueError):
        detector.to_frame(sample)


def test_cli_rejects_network_record_of_wrong_length() -> None:
    with pytest.raises(ValueError):
        parse_network_record("1,2,3")


def test_cli_rejects_non_numeric_network_value() -> None:
    values = ",".join(["tcp"] * 41)
    with pytest.raises(ValueError):
        parse_network_record(values)


# --------------------------------------------------------- CLI rendering


def test_cli_render_never_crashes_on_garbage(capsys: pytest.CaptureFixture) -> None:
    import io

    out = io.StringIO()
    for line in ["1,2,3", "x" * 300, "http://", "🎉"]:
        render(line, out, colour=False)
    text = out.getvalue()
    assert "INPUT ERROR" in text or "NOT ANALYSED" in text or "SAFE" in text
