"""Network intrusion detector: predict(record) -> {"label", "confidence"}.

Input: one NSL-KDD connection as a dict with the 41 feature names as keys
(see ``FEATURE_COLUMNS`` in ``src/utils/network_preprocessor.py``). Text fields
(``protocol_type``, ``service``, ``flag``) are strings; the rest are numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from src.detectors.base import ThreatDetector, load_bundle
from src.utils.network_preprocessor import FEATURE_COLUMNS, TEXT_COLUMNS

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "network_detector.pkl"


class NetworkDetector(ThreatDetector):
    domain = "network"
    label_names = ("normal", "attack")

    def to_frame(self, sample: Mapping[str, Any]) -> pd.DataFrame:
        missing = [name for name in FEATURE_COLUMNS if name not in sample]
        if missing:
            raise KeyError(
                f"Missing network fields: {missing[:5]} ({len(missing)} in total)"
            )
        row: dict[str, Any] = {}
        for name in FEATURE_COLUMNS:
            row[name] = (
                str(sample[name]) if name in TEXT_COLUMNS else float(sample[name])
            )
        return pd.DataFrame([row], columns=list(FEATURE_COLUMNS))


def load_network_detector(path: Path = MODEL_PATH) -> NetworkDetector:
    return NetworkDetector(load_bundle(path))
