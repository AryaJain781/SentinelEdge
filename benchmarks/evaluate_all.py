"""Official benchmark: score the three saved detectors on their test splits.

Run from the project root::

    python -m benchmarks.evaluate_all

What it does, for each domain:

1. Loads the saved model ``models/<domain>_detector.pkl`` (trained on the train
   split, with hyperparameters tuned on the validation split).
2. Scores the test split and records precision, recall, F1, the false-negative
   rate and the confusion matrix.
3. Measures the median single-prediction latency through the detector's own
   ``predict()``, including preprocessing.
4. Measures memory: the file size on disk, and the peak Python memory
   (tracemalloc) while loading the model and making 200 predictions.

No model is changed by this script. The results are written to
``docs/benchmark_summary.md`` and ``benchmarks/results/official.json``.

Note: the test split was already scored once in Phase 3, for the model
report. This run repeats that scoring on the same saved models, so it should
reproduce the Phase 3 numbers exactly. It does not add new evidence on new
data.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np

from src.detectors.base import (
    MAX_LATENCY_MS,
    MAX_MODEL_MB,
    compute_metrics,
    file_size_mb,
    load_bundle,
    measure_latency_ms,
)
from src.detectors.network_detector import NetworkDetector
from src.detectors.sms_detector import SMSDetector
from src.detectors.train_detectors import load_split
from src.detectors.url_detector import URLDetector

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS = PROJECT_ROOT / "models"
RESULTS_JSON = PROJECT_ROOT / "benchmarks" / "results" / "official.json"
SUMMARY_MD = PROJECT_ROOT / "docs" / "benchmark_summary.md"
DETECTORS = {"url": URLDetector, "sms": SMSDetector, "network": NetworkDetector}
SMS_SAMPLE = (
    "URGENT! Your bank account is suspended. Share your OTP now: http://bit.ly/x1"
)


def _sample_for(domain: str, features) -> Any:
    row = features.iloc[0]
    if domain == "sms":
        return SMS_SAMPLE
    if domain == "url":
        return {k: float(v) for k, v in row.items()}
    from src.utils.network_preprocessor import TEXT_COLUMNS

    return {k: (str(v) if k in TEXT_COLUMNS else float(v)) for k, v in row.items()}


def evaluate_domain(domain: str) -> dict[str, Any]:
    model_path = MODELS / f"{domain}_detector.pkl"
    if not model_path.exists():
        raise FileNotFoundError(
            f"{model_path} is missing. Run the Phase 3 training first."
        )

    features, labels = load_split(domain, "test")
    y_true = labels.to_numpy()

    tracemalloc.start()
    bundle = load_bundle(model_path)
    detector = DETECTORS[domain](bundle)
    sample = _sample_for(domain, features)
    for _ in range(200):
        detector.predict(sample)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    prob = bundle["pipeline"].predict_proba(features)[:, 1]
    y_pred = (prob >= bundle["threshold"]).astype(int)
    metrics = compute_metrics(y_true, y_pred)
    latency = measure_latency_ms(detector.predict, sample)

    return {
        "domain": domain,
        "model": bundle["model_name"],
        "threshold": float(bundle["threshold"]),
        "test_rows": int(len(y_true)),
        "test_positive_share": float(np.mean(y_true)),
        "metrics": metrics,
        "latency_median_ms": latency["median_ms"],
        "latency_p95_ms": latency["p95_ms"],
        "file_size_mb": file_size_mb(model_path),
        "peak_python_memory_mb": peak_bytes / 1_000_000,
        "within_latency": latency["median_ms"] < MAX_LATENCY_MS,
        "within_size": file_size_mb(model_path) < MAX_MODEL_MB,
    }


def _matches_phase3(result: dict[str, Any]) -> str:
    report = MODELS / "results.json"
    if not report.exists():
        return "not checked (models/results.json missing)"
    records = json.loads(report.read_text(encoding="utf-8"))
    for record in records:
        if record["domain"] != result["domain"]:
            continue
        chosen = record["families"][record["chosen_family"]]["test"]
        same = abs(chosen["f1"] - result["metrics"]["f1"]) < 1e-9
        return "yes" if same else "NO, check the models"
    return "not checked"


def write_outputs(results: list[dict[str, Any]]) -> None:
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    today = dt.date.today().isoformat()
    lines = [
        "# Benchmark Summary (official run)",
        "",
        f"Run date: {today}. Seed 42. Models: saved Phase 3 detectors, unchanged.",
        "",
        "Latency and memory are measured on this PC. Phone numbers come in Phase 4 "
        "measurements.",
        "",
        "| Domain | Model | Test rows | Precision | Recall | F1 | Missed threats | "
        "Latency median (ms) | Size (MB) | Peak memory (MB) | Limits met | "
        "Matches Phase 3 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in results:
        m = r["metrics"]
        limits = "yes" if r["within_latency"] and r["within_size"] else "no"
        lines.append(
            f"| {r['domain']} | {r['model']} | {r['test_rows']:,} | "
            f"{m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | "
            f"{m['false_negative_rate']:.4f} | {r['latency_median_ms']:.2f} | "
            f"{r['file_size_mb']:.2f} | {r['peak_python_memory_mb']:.1f} | "
            f"{limits} | {r['matches_phase3']} |"
        )
    lines += [
        "",
        f"Limits: latency under {MAX_LATENCY_MS:.0f} ms, "
        f"model file under {MAX_MODEL_MB:.0f} MB.",
        "",
        "Confusion matrices (TN / FP / FN / TP):",
        "",
    ]
    for r in results:
        m = r["metrics"]
        lines.append(f"- {r['domain']}: {m['tn']} / {m['fp']} / {m['fn']} / {m['tp']}")
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    results = []
    for domain in ("url", "sms", "network"):
        print(f"[eval] {domain}")
        result = evaluate_domain(domain)
        result["matches_phase3"] = _matches_phase3(result)
        results.append(result)
        m = result["metrics"]
        print(
            f"  P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} "
            f"latency={result['latency_median_ms']:.2f} ms "
            f"size={result['file_size_mb']:.2f} MB"
        )
    write_outputs(results)
    print(f"[docs ] {SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
