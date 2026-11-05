"""Interactive terminal dashboard for the threat detector.

Run from the project root::

    python -m src.ui.cli

Type or paste a text message, a URL, or a network record, then press Enter.
Type ``quit`` to exit. Each answer shows a colour badge, the threat score,
the measured clues and the advice.

Network records are typed as 41 comma-separated values in the order of
``FEATURE_COLUMNS``. Text fields are ``protocol_type``, ``service`` and ``flag``.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, TextIO

from src.pipeline.router import RouterError, analyze, warm_up
from src.utils.network_preprocessor import FEATURE_COLUMNS, TEXT_COLUMNS

RESET = "\033[0m"
BOLD = "\033[1m"
COLOURS = {"threat": "\033[97;41m", "safe": "\033[97;42m", "warn": "\033[30;43m"}
PLAIN = {"threat": "", "safe": "", "warn": ""}
LINE = "-" * 64


def _use_colour(stream: TextIO) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(stream, "isatty") and stream.isatty()


def badge(text: str, kind: str, colour: bool) -> str:
    """A coloured label such as `` THREAT `` (plain text when colour is off)."""
    if not colour:
        return f"[{text}]"
    return f"{BOLD}{COLOURS[kind]} {text} {RESET}"


def parse_network_record(text: str) -> dict[str, Any]:
    """Turn 41 comma-separated values into the dictionary the detector expects."""
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != len(FEATURE_COLUMNS):
        raise ValueError(
            f"A network record needs {len(FEATURE_COLUMNS)} values, got {len(parts)}"
        )
    record: dict[str, Any] = {}
    for name, value in zip(FEATURE_COLUMNS, parts, strict=True):
        record[name] = value if name in TEXT_COLUMNS else float(value)
    return record


def classify_line(line: str) -> Any:
    """Decide what the user typed: a network record, or text (SMS or URL)."""
    if line.count(",") == len(FEATURE_COLUMNS) - 1:
        return parse_network_record(line), "network"
    return line, "auto"


def render(line: str, out: TextIO, colour: bool) -> None:
    """Analyse one input and print the dashboard block for it."""
    try:
        payload, input_type = classify_line(line)
    except ValueError as exc:
        print(badge("INPUT ERROR", "warn", colour), str(exc), file=out)
        return

    started = time.perf_counter()
    try:
        verdict = analyze(payload, input_type=input_type)
    except RouterError as exc:
        print(badge("INPUT ERROR", "warn", colour), str(exc), file=out)
        return
    except (KeyError, ValueError) as exc:
        print(badge("INPUT ERROR", "warn", colour), str(exc), file=out)
        return
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    print(LINE, file=out)
    if verdict.status == "unsupported":
        print(badge("NOT ANALYSED", "warn", colour), file=out)
        print(f"  {verdict.reason}", file=out)
        print(LINE, file=out)
        return

    if verdict.is_threat:
        print(badge(f"THREAT: {verdict.label.upper()}", "threat", colour), file=out)
    else:
        print(badge("SAFE", "safe", colour), file=out)
    print(f"  Input type     : {verdict.input_type}", file=out)
    if verdict.clues:
        print("  Clues found    :", file=out)
        for clue in verdict.clues:
            print(f"    - {clue}", file=out)
    else:
        print("  Clues found    : none", file=out)
    print(f"  Confidence     : {verdict.confidence:.2f} in '{verdict.label}'", file=out)
    print(
        f"  Threat score   : {verdict.threat_score:.2f} (0 = safe, 1 = threat)",
        file=out,
    )
    print(f"  Detector time  : {elapsed_ms:.1f} ms (target under 15 ms)", file=out)
    print(f"  Model          : {verdict.detector}", file=out)
    if verdict.explanation:
        print("  Advice         :", file=out)
        for advice_line in verdict.explanation.splitlines():
            print(f"    {advice_line}", file=out)
    print(LINE, file=out)


def main(
    argv: list[str] | None = None, stdin: TextIO = sys.stdin, out: TextIO = sys.stdout
) -> int:
    colour = _use_colour(out)
    warm_up()
    print(
        (
            f"{BOLD}SentinelEdge threat checker{RESET}"
            if colour
            else "SentinelEdge threat checker"
        ),
        file=out,
    )
    print(
        "Paste an SMS, a URL, or 41 comma-separated network values. "
        "Type 'quit' to exit.",
        file=out,
    )
    while True:
        print("> ", end="", file=out, flush=True)
        line = stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in {"quit", "exit"}:
            break
        render(line, out, colour)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
