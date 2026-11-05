"""Unified router: one entry point, ``analyze(input_data)``, for all detectors.

Flow for every input:

1. Work out the input type (URL, SMS or network record), or use the type given.
2. Send it to the matching detector. The detector makes the threat decision.
3. If it is a threat, build a prompt and ask the explainer for guidance.
4. Check the guidance. If it is not valid, use the fixed template instead.

Raw web addresses are not analysed yet. The URL detector needs the 85 URL
columns from the Mendeley dataset (ADR-0012), and turning an address into those
columns is not implemented. Such input returns status ``unsupported``, with a
reason, rather than a guess.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from src.detectors.base import ThreatDetector
from src.detectors.network_detector import MODEL_PATH as NETWORK_MODEL
from src.detectors.network_detector import load_network_detector
from src.detectors.sms_detector import MODEL_PATH as SMS_MODEL
from src.detectors.sms_detector import load_sms_detector
from src.detectors.url_detector import MODEL_PATH as URL_MODEL
from src.detectors.url_detector import load_url_detector
from src.explainer.prompt_builder import build_prompt, validate_advisory
from src.explainer.runtime import LLMRunner, RunnerUnavailable, TemplateRunner
from src.utils.sms_preprocessor import extract_sms_metadata

InputType = Literal["auto", "url", "sms", "network"]
THREAT_LABELS = frozenset({"phishing", "spam", "attack"})
_URL_TOKEN = re.compile(
    r"^(?:https?://|www\.)\S+$|^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?$", re.I
)
_NETWORK_MARKER_FIELDS = ("protocol_type", "service", "flag", "src_bytes")
_URL_MARKER_FIELDS = ("length_url", "qty_dot_url")


@dataclass(frozen=True)
class Verdict:
    """The result of analysing one input."""

    status: Literal["ok", "unsupported"]
    input_type: str
    is_threat: bool
    label: str
    confidence: float
    threat_score: float
    detector: str
    explanation: str | None
    explanation_source: str | None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "input_type": self.input_type,
            "is_threat": self.is_threat,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "threat_score": round(self.threat_score, 4),
            "detector": self.detector,
            "explanation": self.explanation,
            "explanation_source": self.explanation_source,
            "reason": self.reason,
        }


class RouterError(ValueError):
    """Raised for input that does not match the type the caller asked for."""


@lru_cache(maxsize=1)
def _detectors() -> dict[str, ThreatDetector]:
    """Load each detector once; the first call takes about a second."""
    loaded: dict[str, ThreatDetector] = {}
    if URL_MODEL.exists():
        loaded["url"] = load_url_detector()
    if SMS_MODEL.exists():
        loaded["sms"] = load_sms_detector()
    if NETWORK_MODEL.exists():
        loaded["network"] = load_network_detector()
    return loaded


def warm_up() -> None:
    """Load every detector now, so the first real request is not slow."""
    _detectors()


def detect_input_type(input_data: Any) -> str:
    """Guess the input type. Returns "url", "sms" or "network"."""
    if isinstance(input_data, Mapping):
        if any(field in input_data for field in _NETWORK_MARKER_FIELDS):
            return "network"
        if any(field in input_data for field in _URL_MARKER_FIELDS):
            return "url"
        raise RouterError("Dictionary input matches neither a network nor a URL record")
    if isinstance(input_data, str):
        text = input_data.strip()
        if text and " " not in text:
            if text.lower().startswith(("http://", "https://", "www.")):
                return "url"
            if _URL_TOKEN.match(text):
                return "url"
        return "sms"
    raise RouterError(f"Unsupported input type: {type(input_data).__name__}")


def _clues_for(input_type: str, input_data: Any) -> list[str]:
    """Short facts computed by our code. They never contain untrusted text."""
    if input_type == "sms":
        meta = extract_sms_metadata(input_data)
        clues = []
        if meta["has_url"]:
            clues.append("the message contains a link")
        if meta["has_phone"]:
            clues.append("the message contains a phone number")
        if meta["has_currency"]:
            clues.append("the message mentions money")
        if meta["urgency_count"]:
            clues.append(f"{int(meta['urgency_count'])} urgency word(s) found")
        if meta["financial_count"]:
            clues.append(
                f"{int(meta['financial_count'])} money or account word(s) found"
            )
        return clues
    if input_type == "network":
        return [
            f"protocol: {input_data.get('protocol_type', 'unknown')}",
            f"service: {input_data.get('service', 'unknown')}",
        ]
    return ["URL features were supplied as numbers"]


def _advisory_for(
    input_type: str,
    input_data: Any,
    label: str,
    threat_score: float,
    runner: LLMRunner,
) -> tuple[str, str]:
    """Return (advisory_text, source). Falls back to the template when needed."""
    untrusted = input_data if isinstance(input_data, str) else ""
    prompt = build_prompt(
        label, threat_score, _clues_for(input_type, input_data), untrusted
    )
    try:
        candidate = runner.generate(prompt)
    except RunnerUnavailable:
        candidate = ""
    ok, _ = validate_advisory(candidate, is_threat=True)
    if ok:
        return candidate, runner.name
    fallback = TemplateRunner().generate(prompt)
    return fallback, "template (fallback)"


def analyze(
    input_data: Any,
    input_type: InputType = "auto",
    explain: bool = True,
    runner: LLMRunner | None = None,
) -> Verdict:
    """Analyse one input and return a Verdict.

    The detector decides ``is_threat``. The explainer only adds words.
    """
    detected = detect_input_type(input_data) if input_type == "auto" else input_type
    if input_type != "auto" and detect_input_type(input_data) != input_type:
        raise RouterError(f"Input does not look like a {input_type} record")

    if detected == "url" and isinstance(input_data, str):
        return Verdict(
            status="unsupported",
            input_type="url",
            is_threat=False,
            label="unknown",
            confidence=0.0,
            threat_score=0.0,
            detector="none",
            explanation=None,
            explanation_source=None,
            reason=(
                "Raw web addresses are not analysed yet. The URL model needs the "
                "85 URL columns, which are not computed from addresses in this build."
            ),
        )

    detector = _detectors().get(detected)
    if detector is None:
        raise RouterError(f"No trained model is available for {detected} input")

    result = detector.predict(input_data)
    label = result["label"]
    confidence = float(result["confidence"])
    is_threat = label in THREAT_LABELS
    threat_score = confidence if is_threat else 1.0 - confidence

    explanation = None
    source = None
    if explain and is_threat:
        if runner is None:
            runner = TemplateRunner()
        explanation, source = _advisory_for(
            detected, input_data, label, threat_score, runner
        )

    return Verdict(
        status="ok",
        input_type=detected,
        is_threat=is_threat,
        label=label,
        confidence=confidence,
        threat_score=threat_score,
        detector=detector.bundle.get("model_name", detected),
        explanation=explanation,
        explanation_source=source,
    )
