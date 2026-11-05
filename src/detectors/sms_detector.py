"""SMS scam detector: predict(text) -> {"label", "confidence"}.

Input: the raw SMS text as a string. The detector cleans the text and computes
the metadata itself, using the same functions as the training data.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.detectors.base import ThreatDetector, load_bundle
from src.utils.sms_preprocessor import (
    SMS_METADATA_NAMES,
    clean_sms,
    extract_sms_metadata,
)

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "sms_detector.pkl"
TEXT_COLUMN = "text_clean"


class SMSDetector(ThreatDetector):
    domain = "sms"
    label_names = ("ham", "spam")

    def to_frame(self, sample: str) -> pd.DataFrame:
        if not isinstance(sample, str):
            raise TypeError("SMS detector expects the raw message as a string")
        row = {TEXT_COLUMN: clean_sms(sample)}
        row.update(extract_sms_metadata(sample))
        columns = [TEXT_COLUMN, *SMS_METADATA_NAMES]
        return pd.DataFrame([row], columns=columns)


def load_sms_detector(path: Path = MODEL_PATH) -> SMSDetector:
    return SMSDetector(load_bundle(path))
