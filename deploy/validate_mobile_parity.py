"""Check that an exported mobile artifact matches the original PC pipeline.

Status: **written but not executed in this environment** — same reason as
`deploy/export_detectors.py`: no trained models and no `onnxruntime`-ready
export exist in the sandbox this was authored in. Run this after
`export_detectors.py`, on the same machine, before trusting any exported
file enough to push it to a phone.

What "parity" means here, precisely, so this script's pass/fail is not
ambiguous:

1. **Accuracy parity.** Run the ORIGINAL scikit-learn pipeline and the
   EXPORTED artifact (ONNX via onnxruntime, or the identical joblib bundle
   for a Chaquopy fallback) on the same held-out test split
   (`data/processed/<domain>/test.csv`). Compare accuracy, precision,
   recall and F1 using the exact same `compute_metrics()` function already
   used for every number in `docs/benchmark_summary.md`, so these figures
   are comparable to that document, not a new ad hoc metric.
2. **Degradation budget: < 1 percentage point of accuracy**, per the Phase 8
   brief. This script computes ``abs(original_accuracy - exported_accuracy)``
   and exits with a non-zero status, printing which domain failed, if any
   domain exceeds 0.01. It does not average across domains or hide a single
   bad domain behind an overall pass.
3. **Latency** is also reported (median over repeated single-row calls
   through onnxruntime), but this script does not gate on it — Section 4 of
   the Phase 8 brief's 25 ms classical-verdict budget must be measured
   on-device, not through onnxruntime on a PC, because PC and phone timings
   are known to differ (every prior benchmark in this project says so).
   Treat the latency number this script prints as a sanity check only.

For the Chaquopy fallback case (the SMS detector, if ONNX export failed in
`export_detectors.py`): there is no conversion to validate, because the
exact same joblib pipeline is being run. This script still runs it, mainly
so the test-set evaluation pathway is exercised and the reported numbers
land in the same report either way — expect 0.0 accuracy delta there.

Usage::

    python -m deploy.validate_mobile_parity --domain all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
MOBILE_DIR = MODELS_DIR / "mobile"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

ACCURACY_DEGRADATION_BUDGET = 0.01  # 1 percentage point, per the Phase 8 brief

sys.path.insert(0, str(PROJECT_ROOT))  # allow `from src...` imports below

from src.detectors.base import compute_metrics  # noqa: E402
from src.detectors.train_detectors import load_split  # noqa: E402


def _load_manifest(domain: str) -> dict[str, Any]:
    candidates = list(MOBILE_DIR.glob(f"{domain}_detector*.manifest.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No manifest found for domain '{domain}' in {MOBILE_DIR}. "
            "Run `python -m deploy.export_detectors` first."
        )
    with candidates[0].open() as fh:
        return json.load(fh)


def _original_predictions(domain: str, features: pd.DataFrame) -> tuple[np.ndarray, dict]:
    bundle = joblib.load(MODELS_DIR / f"{domain}_detector.pkl")
    pipeline = bundle["pipeline"]
    threshold = float(bundle.get("threshold", 0.5))
    probs = pipeline.predict_proba(features)[:, 1]
    labels = (probs >= threshold).astype(int)

    def predict_one(row: pd.DataFrame) -> int:
        p = pipeline.predict_proba(row)[0, 1]
        return int(p >= threshold)

    timing = _time_calls(lambda: predict_one(features.iloc[[0]]))
    return labels, timing


def _onnx_predictions(
    domain: str, manifest: dict[str, Any], features: pd.DataFrame
) -> tuple[np.ndarray, dict]:
    import onnxruntime as ort

    artifact_path = MOBILE_DIR / manifest["artifact"]
    session = ort.InferenceSession(str(artifact_path))
    input_spec = manifest["input_spec"]

    def build_feed(row: pd.DataFrame) -> dict[str, np.ndarray]:
        feed = {}
        for name, spec in input_spec.items():
            dtype = spec["dtype"]
            value = row[name].to_numpy()
            if dtype == "string":
                feed[name] = value.astype(str).reshape(-1, 1)
            else:
                feed[name] = value.astype(np.float32).reshape(-1, 1)
        return feed

    # Single combined 'input' tensor (url domain) vs. one input per column
    # (sms/network) are both handled by build_feed, since input_spec encodes
    # exactly what export_detectors.py produced.
    all_labels = []
    for i in range(len(features)):
        row = features.iloc[[i]]
        if "input" in input_spec:
            feed = {"input": row.to_numpy().astype(np.float32)}
        else:
            feed = build_feed(row)
        outputs = session.run(None, feed)
        # skl2onnx classifiers typically output [labels, probabilities]
        label = int(outputs[0][0])
        all_labels.append(label)

    timing = _time_calls(
        lambda: session.run(
            None,
            {"input": features.iloc[[0]].to_numpy().astype(np.float32)}
            if "input" in input_spec
            else build_feed(features.iloc[[0]]),
        )
    )
    return np.asarray(all_labels), timing


def _chaquopy_predictions(
    domain: str, manifest: dict[str, Any], features: pd.DataFrame
) -> tuple[np.ndarray, dict]:
    artifact_path = MOBILE_DIR / manifest["artifact"]
    bundle = joblib.load(artifact_path)
    pipeline = bundle["pipeline"]
    threshold = float(bundle.get("threshold", 0.5))
    probs = pipeline.predict_proba(features)[:, 1]
    labels = (probs >= threshold).astype(int)
    timing = _time_calls(
        lambda: pipeline.predict_proba(features.iloc[[0]])[0, 1] >= threshold
    )
    return labels, timing


def _time_calls(fn, repeats: int = 100, warmup: int = 10) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - start) * 1000.0)
    arr = np.asarray(timings)
    return {"median_ms": float(np.median(arr)), "p95_ms": float(np.percentile(arr, 95))}


def validate_domain(domain: str) -> bool:
    """Returns True if the domain is within the accuracy degradation budget."""
    features, labels = load_split(domain, "test")
    manifest = _load_manifest(domain)

    original_preds, original_timing = _original_predictions(domain, features)
    original_metrics = compute_metrics(labels.to_numpy(), original_preds)

    if manifest["artifact"].endswith(".onnx"):
        exported_preds, exported_timing = _onnx_predictions(domain, manifest, features)
    else:
        exported_preds, exported_timing = _chaquopy_predictions(domain, manifest, features)
    exported_metrics = compute_metrics(labels.to_numpy(), exported_preds)

    delta = abs(original_metrics["accuracy"] - exported_metrics["accuracy"])
    passed = delta <= ACCURACY_DEGRADATION_BUDGET

    print(f"\n=== {domain} ===")
    print(f"  Original  (PC pipeline) accuracy: {original_metrics['accuracy']:.4f}, "
          f"latency median {original_timing['median_ms']:.2f} ms")
    print(f"  Exported  ({manifest['artifact']}) accuracy: {exported_metrics['accuracy']:.4f}, "
          f"latency median {exported_timing['median_ms']:.2f} ms (PC-side onnxruntime timing, "
          f"NOT a phone measurement)")
    print(f"  Accuracy delta: {delta:.4f} "
          f"({'within' if passed else 'EXCEEDS'} the {ACCURACY_DEGRADATION_BUDGET:.0%} budget)")
    if not passed:
        print(
            f"  FAIL: {domain} exceeds the 1% accuracy-degradation budget. "
            "Do not ship this exported artifact as-is -- investigate the "
            "divergence (see export_detectors.py's module docstring for the "
            "known TF-IDF/ONNX risk on the sms domain) before proceeding to "
            "WP8 Android integration.",
            file=sys.stderr,
        )
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain", choices=("url", "sms", "network", "all"), default="all"
    )
    args = parser.parse_args(argv)
    domains = ("url", "sms", "network") if args.domain == "all" else (args.domain,)

    results = {domain: validate_domain(domain) for domain in domains}
    if all(results.values()):
        print("\nALL DOMAINS WITHIN BUDGET. Safe to proceed to Android integration.")
        return 0
    failed = [d for d, ok in results.items() if not ok]
    print(f"\nFAILED domains: {failed}. Do not proceed to WP8 Android integration "
          "for these until fixed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
