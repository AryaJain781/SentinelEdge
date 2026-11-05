"""Shared pieces for the three detectors: the predict wrapper, metrics, latency
measurement and saving or loading a model bundle.

A saved model is a joblib file (``models/<domain>_detector.pkl``) holding a
dict, which we call a *bundle*:

* ``pipeline``: the fitted scikit-learn pipeline,
* ``threshold``: the probability above which we call the sample a threat,
* ``feature_names``: the input columns the pipeline expects,
* ``domain``, ``model_name``, ``labels`` and ``seed``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

SEED = 42
MAX_LATENCY_MS = 15.0
MAX_MODEL_MB = 25.0


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Precision, recall, F1, false-negative rate and the confusion matrix.

    The positive class is 1 (threat). The false-negative rate is the share of
    real threats that were missed: FN / (FN + TP).
    """
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", pos_label=1, zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    missed = fn / (fn + tp) if (fn + tp) else 0.0
    accuracy = (tp + tn) / len(y_true) if len(y_true) else 0.0
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_negative_rate": float(missed),
        "accuracy": float(accuracy),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def measure_latency_ms(
    predict_one: Callable[[Any], Any], sample: Any, repeats: int = 200, warmup: int = 20
) -> dict[str, float]:
    """Time one prediction on one sample, repeated many times.

    Returns the median and 95th-percentile time in milliseconds. These are
    PC measurements. Phone numbers will differ and must be measured on the device.
    """
    for _ in range(warmup):
        predict_one(sample)
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        predict_one(sample)
        timings.append((time.perf_counter() - start) * 1000.0)
    arr = np.asarray(timings)
    return {
        "median_ms": float(np.median(arr)),
        "p95_ms": float(np.percentile(arr, 95)),
    }


def file_size_mb(path: Path) -> float:
    """Size of a file on disk in megabytes (1 MB = 1,000,000 bytes)."""
    return path.stat().st_size / 1_000_000


def save_bundle(bundle: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)


def load_bundle(path: Path) -> dict[str, Any]:
    return joblib.load(path)


def positive_label_confidence(
    prob_threat: float, threshold: float
) -> tuple[int, float]:
    """Turn P(threat) into (label, confidence).

    The label is 1 when P(threat) >= threshold. Confidence is the probability of
    the label that was chosen, so it is always between 0.5 and 1.0 for a
    threshold of 0.5.
    """
    label = int(prob_threat >= threshold)
    confidence = prob_threat if label == 1 else 1.0 - prob_threat
    return label, float(confidence)


class ThreatDetector:
    """Base class: subclasses define how raw input becomes a DataFrame row."""

    domain: str = ""
    label_names: tuple[str, str] = ("benign", "threat")

    def __init__(self, bundle: dict[str, Any]) -> None:
        self.bundle = bundle
        self.pipeline = bundle["pipeline"]
        self.threshold = float(bundle.get("threshold", 0.5))

    def to_frame(self, sample: Any):  # pragma: no cover - overridden
        raise NotImplementedError

    def predict(self, sample: Any) -> dict[str, Any]:
        """Return ``{"label": str, "confidence": float}`` for one raw sample."""
        frame = self.to_frame(sample)
        prob_threat = float(self.pipeline.predict_proba(frame)[0, 1])
        label, confidence = positive_label_confidence(prob_threat, self.threshold)
        return {"label": self.label_names[label], "confidence": confidence}
