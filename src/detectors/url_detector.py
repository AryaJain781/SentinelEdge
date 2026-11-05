"""URL phishing detector: predict(features) -> {"label", "confidence"}.

Input: a dict holding the 85 URL-only feature values (the columns kept from
the Mendeley dataset, see ADR-0012). Missing features raise a clear error.

Note: this detector does not take a raw web address. Turning an address into
the 85 columns on the phone is a separate task (Phase 4). The 18-clue
extractor in ``src/utils/url_features.py`` is a different, explainable set.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from src.detectors.base import ThreatDetector, load_bundle

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "url_detector.pkl"


class URLDetector(ThreatDetector):
    domain = "url"
    label_names = ("legitimate", "phishing")

    def to_frame(self, sample: Mapping[str, Any]) -> pd.DataFrame:
        names = self.bundle["feature_names"]
        missing = [name for name in names if name not in sample]
        if missing:
            raise KeyError(
                f"Missing URL features: {missing[:5]} ({len(missing)} in total)"
            )
        row = {name: _finite_float(name, sample[name]) for name in names}
        return pd.DataFrame([row], columns=names)


def _finite_float(name: str, value: Any) -> float:
    """Convert to float and reject values that are not real numbers."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"URL feature '{name}' must be a number, got {value!r}"
        ) from exc
    if not math.isfinite(number):
        raise ValueError(f"URL feature '{name}' must be finite, got {value!r}")
    return number


def load_url_detector(path: Path = MODEL_PATH) -> URLDetector:
    return URLDetector(load_bundle(path))
