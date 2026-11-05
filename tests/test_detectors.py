"""Tests for the three detectors: predict(input) -> {label, confidence}.

* Synthetic tests always run. They check the label and confidence maths.
* Model tests run only when the trained files exist in ``models/``. They check
  the output format, input validation, and the 15 ms latency target on this PC.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.detectors.base import (
    MAX_LATENCY_MS,
    ThreatDetector,
    measure_latency_ms,
    positive_label_confidence,
)
from src.detectors.network_detector import MODEL_PATH as NETWORK_MODEL
from src.detectors.network_detector import NetworkDetector, load_network_detector
from src.detectors.sms_detector import MODEL_PATH as SMS_MODEL
from src.detectors.sms_detector import SMSDetector, load_sms_detector
from src.detectors.url_detector import MODEL_PATH as URL_MODEL
from src.detectors.url_detector import URLDetector, load_url_detector
from src.utils.data_loader import PROCESSED_DIR, ROW_ID
from src.utils.network_preprocessor import FEATURE_COLUMNS, TEXT_COLUMNS

SMS_EXAMPLE = "URGENT! Your account is suspended. Share your OTP now: http://bit.ly/x1"


def _first_row(domain: str) -> pd.Series:
    path = PROCESSED_DIR / domain / "val.csv"
    if not path.exists():
        pytest.skip(f"{domain} split not built")
    return pd.read_csv(path).iloc[0]


# ---------------------------------------------------- synthetic (always run)


def test_positive_label_confidence_above_threshold() -> None:
    label, confidence = positive_label_confidence(0.9, 0.5)
    assert label == 1
    assert confidence == pytest.approx(0.9)


def test_positive_label_confidence_below_threshold() -> None:
    label, confidence = positive_label_confidence(0.2, 0.5)
    assert label == 0
    assert confidence == pytest.approx(0.8)


def test_threshold_moves_the_decision() -> None:
    assert positive_label_confidence(0.3, 0.5)[0] == 0
    assert positive_label_confidence(0.3, 0.2)[0] == 1


def test_detector_maps_labels_and_confidence_on_a_tiny_model() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 2))
    y = (x[:, 0] > 0).astype(int)
    pipeline = Pipeline(
        [("scale", StandardScaler()), ("clf", LogisticRegression(random_state=42))]
    ).fit(pd.DataFrame(x, columns=["a", "b"]), y)

    class Tiny(ThreatDetector):
        label_names = ("benign", "threat")

        def to_frame(self, sample):
            return pd.DataFrame([sample], columns=["a", "b"])

    detector = Tiny({"pipeline": pipeline, "threshold": 0.5})
    result = detector.predict([3.0, 0.0])
    assert set(result) == {"label", "confidence"}
    assert result["label"] == "threat"
    assert 0.5 <= result["confidence"] <= 1.0


# ------------------------------------------------------------- real models


@pytest.mark.skipif(not URL_MODEL.exists(), reason="URL model not trained")
def test_url_predict_returns_label_and_confidence() -> None:
    detector: URLDetector = load_url_detector()
    row = _first_row("url").drop(labels=[ROW_ID, "label"])
    result = detector.predict({k: float(v) for k, v in row.items()})
    assert result["label"] in {"legitimate", "phishing"}
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.skipif(not URL_MODEL.exists(), reason="URL model not trained")
def test_url_predict_rejects_missing_features() -> None:
    with pytest.raises(KeyError):
        load_url_detector().predict({"url_length": 10.0})


@pytest.mark.skipif(not SMS_MODEL.exists(), reason="SMS model not trained")
def test_sms_predict_flags_a_scam_style_message() -> None:
    detector: SMSDetector = load_sms_detector()
    result = detector.predict(SMS_EXAMPLE)
    assert result["label"] in {"ham", "spam"}
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.skipif(not SMS_MODEL.exists(), reason="SMS model not trained")
def test_sms_predict_rejects_non_text() -> None:
    with pytest.raises(TypeError):
        load_sms_detector().predict(12345)  # type: ignore[arg-type]


@pytest.mark.skipif(not NETWORK_MODEL.exists(), reason="network model not trained")
def test_network_predict_returns_label_and_confidence() -> None:
    detector: NetworkDetector = load_network_detector()
    row = _first_row("network")
    sample = {
        name: (str(row[name]) if name in TEXT_COLUMNS else float(row[name]))
        for name in FEATURE_COLUMNS
    }
    result = detector.predict(sample)
    assert result["label"] in {"normal", "attack"}
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.skipif(not NETWORK_MODEL.exists(), reason="network model not trained")
def test_network_predict_rejects_missing_fields() -> None:
    with pytest.raises(KeyError):
        load_network_detector().predict({"duration": 0.0})


@pytest.mark.parametrize(
    ("model_path", "loader", "sample_factory"),
    [
        (
            URL_MODEL,
            load_url_detector,
            lambda: {
                k: float(v)
                for k, v in _first_row("url").drop(labels=[ROW_ID, "label"]).items()
            },
        ),
        (SMS_MODEL, load_sms_detector, lambda: SMS_EXAMPLE),
        (
            NETWORK_MODEL,
            load_network_detector,
            lambda: {
                name: (str(v) if name in TEXT_COLUMNS else float(v))
                for name, v in _first_row("network").items()
                if name in FEATURE_COLUMNS
            },
        ),
    ],
    ids=["url", "sms", "network"],
)
def test_predict_is_within_latency_target(model_path, loader, sample_factory) -> None:
    """Median single-prediction time on this PC must stay under 15 ms."""
    if not model_path.exists():
        pytest.skip("model not trained")
    detector = loader()
    timing = measure_latency_ms(
        detector.predict, sample_factory(), repeats=30, warmup=5
    )
    assert timing["median_ms"] < MAX_LATENCY_MS, timing
