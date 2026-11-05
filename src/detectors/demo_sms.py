"""Live demo: ask the SMS detector about one or more messages.

Run from the project root::

    python -m src.detectors.demo_sms
    python -m src.detectors.demo_sms "Your OTP is 4821. Do not share it."
"""

from __future__ import annotations

import sys

from src.detectors.sms_detector import load_sms_detector

EXAMPLES = [
    "Hi, are we still meeting for lunch at 1pm?",
    "URGENT! Your bank account is suspended. Share your OTP now: http://bit.ly/x1",
    "You have won a prize of Rs 50000. Claim it today at http://win-cash.xyz",
]


def main(argv: list[str] | None = None) -> int:
    messages = argv if argv else EXAMPLES
    detector = load_sms_detector()
    for message in messages:
        result = detector.predict(message)
        print(f"Message : {message}")
        print(f"Output  : {result}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
