"""Language-model runners: one interface, three implementations.

* ``TemplateRunner``: a fixed, rule-based advisory. It is not a language model.
  It is used on a PC for offline prompt validation and as the safe fallback.
* ``ExecuTorchRunner``: runs the 4-bit Llama 3.2 1B ``.pte`` file on the target
  device through the ExecuTorch runtime. It is a stub here, because the model
  file and runtime are not installed on this PC (Phase 6).

Every runner receives the same ``PromptPair``. The pipeline checks the output
with ``validate_advisory`` whatever runner produced it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.explainer.prompt_builder import PromptPair


class RunnerUnavailable(RuntimeError):
    """Raised when a runner cannot run on this machine."""


class LLMRunner(Protocol):
    name: str

    def generate(self, prompt: PromptPair) -> str: ...


_MECHANISMS = {
    "phishing": "This link imitates a trusted site to steal your login details.",
    "spam": "This message uses urgency or a reward to push you into acting fast.",
    "attack": "This traffic matches an attack that can overload or probe your device.",
}


class TemplateRunner:
    """Deterministic advisory built from the verdict and the measured facts only.

    It never reads the untrusted text, so no injected instruction can reach it.
    """

    name = "template"

    _STEPS = {
        "phishing": (
            "1. Do not click any link in this message.",
            "2. Open the official app or website yourself, by typing its address.",
            "3. Report the message as phishing to your bank or service provider.",
        ),
        "spam": (
            "1. Do not reply, and do not click any link.",
            "2. Never share an OTP, PIN or password with anyone who asks by text.",
            "3. Block the sender and report the message as spam.",
        ),
        "attack": (
            "1. Block the source address at the firewall or on the device.",
            "2. Check the device for unusual processes or open ports.",
            "3. Report the traffic to the network administrator.",
        ),
    }

    def generate(self, prompt: PromptPair) -> str:
        label = _label_from_prompt(prompt.user)
        if label not in self._STEPS:
            return "This looks normal. No action is needed."
        mechanism = _MECHANISMS[label]
        steps = "\n".join(self._STEPS[label])
        return f"What is happening: {mechanism}\n\nWhat to do:\n{steps}"


def _label_from_prompt(user_prompt: str) -> str:
    for line in user_prompt.splitlines():
        if line.startswith("Verdict (authoritative):"):
            return line.split(":", 1)[1].strip()
    return ""


class ExecuTorchRunner:
    """Runs the Llama 3.2 1B .pte model on the device through ExecuTorch."""

    name = "executorch-llama-3.2-1b"

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        if not model_path.exists():
            raise RunnerUnavailable(f"Model file not found: {model_path} (Phase 6)")
        try:
            import executorch  # noqa: F401
        except ImportError as exc:
            raise RunnerUnavailable(
                "ExecuTorch runtime is not installed on this machine (Phase 6)"
            ) from exc
        raise RunnerUnavailable("ExecuTorch generation is wired in Phase 6")

    def generate(self, prompt: PromptPair) -> str:  # pragma: no cover - stub
        raise RunnerUnavailable("ExecuTorch generation is wired in Phase 6")
