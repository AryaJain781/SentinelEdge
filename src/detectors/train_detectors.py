"""Train, tune and evaluate the baseline and improved detectors for each domain.

Protocol (the same for every domain):

1. Fit every candidate on the TRAIN split only.
2. Tune hyperparameters and the URL decision threshold on the VALIDATION split.
3. Pick one candidate per family (baseline, improved) by validation F1.
4. Keep the candidate that passes the size and latency limits with the best
   validation F1 as ``models/<domain>_detector.pkl``.
5. Score the two final candidates on the TEST split exactly once, for reporting.
   The test split does not influence any choice above.

Run from the project root::

    python -m src.detectors.train_detectors                 # all domains
    python -m src.detectors.train_detectors --domain sms    # one domain
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.detectors.base import (
    MAX_LATENCY_MS,
    MAX_MODEL_MB,
    SEED,
    ThreatDetector,
    compute_metrics,
    file_size_mb,
    load_bundle,
    measure_latency_ms,
    save_bundle,
)
from src.detectors.network_detector import NetworkDetector
from src.detectors.sms_detector import SMSDetector
from src.detectors.url_detector import URLDetector
from src.utils.data_loader import LABEL, PROCESSED_DIR, ROW_ID
from src.utils.network_preprocessor import FEATURE_COLUMNS, TEXT_COLUMNS
from src.utils.sms_preprocessor import SMS_METADATA_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
CANDIDATE_DIR = MODELS_DIR / "candidates"
DOCS_DIR = PROJECT_ROOT / "docs"
MODEL_CARD_DIR = DOCS_DIR / "model_cards"
TRAIN_DATE = dt.date(2026, 11, 5).isoformat()

URL_TARGET_RECALL = 0.98  # ADR-0011: favour recall for phishing URLs
SMS_TEXT = "text_clean"
DOMAINS = {
    "url": (URLDetector, "phishing", ("legitimate", "phishing")),
    "sms": (SMSDetector, "spam", ("ham", "spam")),
    "network": (NetworkDetector, "attack", ("normal", "attack")),
}
SAMPLE_SMS = "URGENT! Your account is suspended. Share your OTP now: http://bit.ly/x1"


@dataclass
class Candidate:
    """One fitted model with its hyperparameter value and validation scores."""

    family: str  # "baseline" or "improved"
    param: str  # printable hyperparameter, e.g. "C=1.0"
    pipeline: Pipeline
    threshold: float
    val_metrics: dict[str, float]
    val_prob: np.ndarray


# ------------------------------------------------------------------ data


def load_split(domain: str, split: str) -> tuple[pd.DataFrame, pd.Series]:
    """Return (features, labels) for one processed split."""
    frame = pd.read_csv(PROCESSED_DIR / domain / f"{split}.csv")
    labels = frame[LABEL].astype(int)
    if domain == "url":
        features = frame.drop(columns=[ROW_ID, LABEL])
    elif domain == "sms":
        features = frame[[SMS_TEXT, *SMS_METADATA_NAMES]].copy()
        features[SMS_TEXT] = features[SMS_TEXT].fillna("").astype(str)
    else:
        features = frame[list(FEATURE_COLUMNS)].copy()
        for column in TEXT_COLUMNS:
            features[column] = features[column].astype(str)
    return features, labels


def feature_names(domain: str, features: pd.DataFrame) -> list[str]:
    return list(features.columns)


# ---------------------------------------------------------- pipelines


def _url_pipeline(family: str, value: float | int) -> Pipeline:
    if family == "baseline":
        model = LogisticRegression(C=float(value), max_iter=2000, random_state=SEED)
        return Pipeline([("scale", StandardScaler()), ("clf", model)])
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=int(value),
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=SEED,
    )
    return Pipeline([("clf", model)])


def _sms_pipeline(family: str, value: float) -> Pipeline:
    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    if family == "baseline":
        pre = ColumnTransformer([("text", tfidf, SMS_TEXT)])
        return Pipeline([("pre", pre), ("clf", MultinomialNB(alpha=float(value)))])
    pre = ColumnTransformer(
        [
            ("text", tfidf, SMS_TEXT),
            ("meta", StandardScaler(), list(SMS_METADATA_NAMES)),
        ]
    )
    model = LogisticRegression(C=float(value), max_iter=2000, random_state=SEED)
    return Pipeline([("pre", pre), ("clf", model)])


def _network_pipeline(family: str, value: float | int) -> Pipeline:
    numeric = [c for c in FEATURE_COLUMNS if c not in TEXT_COLUMNS]
    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), list(TEXT_COLUMNS)),
            ("num", StandardScaler(), numeric),
        ]
    )
    if family == "baseline":
        model = LogisticRegression(C=float(value), max_iter=2000, random_state=SEED)
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=int(value),
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=SEED,
        )
    return Pipeline([("pre", pre), ("clf", model)])


PIPELINE_BUILDERS: dict[str, Callable[[str, Any], Pipeline]] = {
    "url": _url_pipeline,
    "sms": _sms_pipeline,
    "network": _network_pipeline,
}

# Hyperparameter grids. Each family is tuned on the validation split only.
GRIDS: dict[str, dict[str, list[Any]]] = {
    "url": {"baseline": [0.1, 1.0, 10.0], "improved": [10, 16]},
    "sms": {"baseline": [0.1, 0.5, 1.0], "improved": [1.0, 10.0]},
    "network": {"baseline": [0.1, 1.0], "improved": [12, 16]},
}


def _param_label(family: str, domain: str, value: Any) -> str:
    if domain == "url" and family == "improved":
        return f"max_depth={value}"
    if domain == "network" and family == "improved":
        return f"max_depth={value}"
    if domain == "sms" and family == "baseline":
        return f"alpha={value}"
    return f"C={value}"


# ---------------------------------------------------------- tuning


def choose_threshold(
    y_true: np.ndarray, prob: np.ndarray, target_recall: float
) -> float:
    """Highest-precision threshold whose validation recall reaches the target.

    Falls back to 0.5 when no threshold reaches the target.
    """
    best_threshold, best_precision = 0.5, -1.0
    for threshold in np.linspace(0.05, 0.95, 91):
        metrics = compute_metrics(y_true, (prob >= threshold).astype(int))
        if metrics["recall"] >= target_recall and metrics["precision"] > best_precision:
            best_threshold, best_precision = float(threshold), metrics["precision"]
    return best_threshold


def _single_thread(pipeline: Pipeline) -> None:
    """Use one thread for prediction.

    Training may use every CPU core, but predicting a single sample with many
    threads adds about 40 ms of overhead. One thread is faster for one sample.
    """
    clf = pipeline.named_steps["clf"]
    if hasattr(clf, "n_jobs"):
        clf.n_jobs = 1


def fit_candidates(domain: str) -> dict[str, list[Candidate]]:
    """Fit every grid point of both families on TRAIN and score it on VALIDATION."""
    x_train, y_train = load_split(domain, "train")
    x_val, y_val = load_split(domain, "val")
    results: dict[str, list[Candidate]] = {}
    for family, values in GRIDS[domain].items():
        built: list[Candidate] = []
        for value in values:
            pipeline = PIPELINE_BUILDERS[domain](family, value)
            pipeline.fit(x_train, y_train)
            _single_thread(pipeline)
            prob = pipeline.predict_proba(x_val)[:, 1]
            if domain == "url":
                threshold = choose_threshold(y_val.to_numpy(), prob, URL_TARGET_RECALL)
            else:
                threshold = 0.5
            metrics = compute_metrics(y_val.to_numpy(), (prob >= threshold).astype(int))
            built.append(
                Candidate(
                    family=family,
                    param=_param_label(family, domain, value),
                    pipeline=pipeline,
                    threshold=threshold,
                    val_metrics=metrics,
                    val_prob=prob,
                )
            )
        results[family] = built
    return results


def best_per_family(candidates: dict[str, list[Candidate]]) -> dict[str, Candidate]:
    """Highest validation F1 inside each family (ties keep the first)."""
    return {
        family: max(options, key=lambda c: c.val_metrics["f1"])
        for family, options in candidates.items()
    }


# ---------------------------------------------------- detector helpers


def _bundle(domain: str, candidate: Candidate, columns: list[str]) -> dict[str, Any]:
    return {
        "pipeline": candidate.pipeline,
        "threshold": candidate.threshold,
        "feature_names": columns,
        "domain": domain,
        "model_name": f"{candidate.family} ({candidate.param})",
        "labels": DOMAINS[domain][2],
        "seed": SEED,
        "trained_on": "train split only; hyperparameters tuned on validation",
    }


def _detector(domain: str, bundle: dict[str, Any]) -> ThreatDetector:
    return DOMAINS[domain][0](bundle)


def _sample_for(domain: str, split_features: pd.DataFrame) -> Any:
    row = split_features.iloc[0]
    if domain == "sms":
        return SAMPLE_SMS
    if domain == "url":
        return {k: float(v) for k, v in row.items()}
    return {k: (str(v) if k in TEXT_COLUMNS else float(v)) for k, v in row.items()}


def _test_metrics(domain: str, candidate: Candidate) -> dict[str, float]:
    x_test, y_test = load_split(domain, "test")
    prob = candidate.pipeline.predict_proba(x_test)[:, 1]
    return compute_metrics(y_test.to_numpy(), (prob >= candidate.threshold).astype(int))


# ------------------------------------------------------------ driver


def run_domain(domain: str) -> dict[str, Any]:
    """Train, select, evaluate and save one domain. Returns a results record."""
    print(f"[train] {domain}: fitting candidates on the train split")
    candidates = fit_candidates(domain)
    finalists = best_per_family(candidates)
    x_val, _ = load_split(domain, "val")
    columns = feature_names(domain, x_val)

    records: dict[str, Any] = {"domain": domain, "families": {}}
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    for family, candidate in finalists.items():
        path = CANDIDATE_DIR / f"{domain}_{family}.pkl"
        bundle = _bundle(domain, candidate, columns)
        save_bundle(bundle, path)
        detector = _detector(domain, bundle)
        sample = _sample_for(domain, x_val)
        latency = measure_latency_ms(detector.predict, sample)
        records["families"][family] = {
            "param": candidate.param,
            "threshold": candidate.threshold,
            "val": candidate.val_metrics,
            "test": _test_metrics(domain, candidate),
            "size_mb": file_size_mb(path),
            "latency": latency,
            "path": str(path),
        }
        print(f"  {family}: {candidate.param} val F1={candidate.val_metrics['f1']:.4f}")

    records["all_validation"] = {
        family: [
            {"param": c.param, "threshold": c.threshold, **c.val_metrics}
            for c in options
        ]
        for family, options in candidates.items()
    }

    eligible = [
        (family, info)
        for family, info in records["families"].items()
        if info["size_mb"] < MAX_MODEL_MB
        and info["latency"]["median_ms"] < MAX_LATENCY_MS
    ]
    pool = eligible or list(records["families"].items())
    chosen_family, chosen_info = max(pool, key=lambda item: item[1]["val"]["f1"])
    records["chosen_family"] = chosen_family
    records["constraints_met"] = bool(eligible)
    chosen_bundle = load_bundle(Path(chosen_info["path"]))
    save_bundle(chosen_bundle, MODELS_DIR / f"{domain}_detector.pkl")
    print(f"[save ] models/{domain}_detector.pkl <- {chosen_family}")
    return records


def write_docs(all_records: list[dict[str, Any]]) -> None:
    """Write the comparison tables and one model card per domain."""
    MODEL_CARD_DIR.mkdir(parents=True, exist_ok=True)
    comparison = DOCS_DIR / "model_comparison.md"
    comparison.write_text(_comparison_markdown(all_records), encoding="utf-8")
    for record in all_records:
        card = MODEL_CARD_DIR / f"{record['domain']}_detector.md"
        card.write_text(_card_markdown(record), encoding="utf-8")
    (MODELS_DIR / "results.json").write_text(
        json.dumps(all_records, indent=2, default=float), encoding="utf-8"
    )


def _row(name: str, info: dict[str, Any], split: str) -> str:
    m = info[split]
    return (
        f"| {name} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | "
        f"{m['false_negative_rate']:.4f} | "
        f"{m['tn']} / {m['fp']} / {m['fn']} / {m['tp']} | "
        f"{info['size_mb']:.2f} | {info['latency']['median_ms']:.3f} |"
    )


def _comparison_markdown(all_records: list[dict[str, Any]]) -> str:
    lines = [
        "# Model Comparison (Phase 3)",
        "",
        f"Trained {TRAIN_DATE} with seed {SEED}. Hyperparameters and thresholds were "
        "chosen on the **validation** split. The **test** split was scored once, "
        "for reporting only.",
        "",
        "Latency is measured on this PC (median of 200 single-sample predictions, "
        "including preprocessing). Phone timings must be measured on the device.",
        "",
        f"Limits: size < {MAX_MODEL_MB:.0f} MB, latency < {MAX_LATENCY_MS:.0f} ms.",
        "",
    ]
    header = (
        "| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | "
        "Size (MB) | Latency (ms, median) |"
    )
    divider = "|---|---:|---:|---:|---:|---:|---:|---:|"
    for record in all_records:
        domain = record["domain"]
        lines += [
            f"## {domain.upper()}",
            "",
            "### Test split (final, reported once)",
            "",
        ]
        lines += [header, divider]
        for family, info in record["families"].items():
            tag = " **(selected)**" if family == record["chosen_family"] else ""
            lines.append(_row(f"{family}: {info['param']}{tag}", info, "test"))
        lines += ["", "### Validation split (used for selection)", ""]
        lines += [header, divider]
        for family, info in record["families"].items():
            lines.append(_row(f"{family}: {info['param']}", info, "val"))
        lines += ["", "### All hyperparameter values tried (validation)", ""]
        lines += ["| Family | Setting | Threshold | Validation F1 | Recall |"]
        lines += ["|---|---|---:|---:|---:|"]
        for family, options in record["all_validation"].items():
            for option in options:
                lines.append(
                    f"| {family} | {option['param']} | {option['threshold']:.2f} | "
                    f"{option['f1']:.4f} | {option['recall']:.4f} |"
                )
        lines.append("")
    return "\n".join(lines) + "\n"


def _card_markdown(record: dict[str, Any]) -> str:
    domain = record["domain"]
    chosen = record["families"][record["chosen_family"]]
    names = {
        "url": "URL phishing detector",
        "sms": "SMS scam detector",
        "network": "Network intrusion detector",
    }
    features = {
        "url": "85 URL-only features from the Mendeley dataset (ADR-0012)",
        "sms": "`text_clean` (TF-IDF, 1-2 grams) plus 8 metadata counts",
        "network": "41 NSL-KDD fields (3 text fields one-hot encoded)",
    }
    met = "met" if record["constraints_met"] else "NOT met (no candidate passed)"
    test = chosen["test"]
    return "\n".join(
        [
            f"# Model card: {names[domain]}",
            "",
            f"- **File:** `models/{domain}_detector.pkl`",
            f"- **Selected model:** {record['chosen_family']} ({chosen['param']})",
            f"- **Trained:** {TRAIN_DATE}",
            f"- **Random seed:** {SEED}",
            f"- **Labels:** {', '.join(DOMAINS[domain][2])} (positive class = 1, "
            f"{DOMAINS[domain][2][1]})",
            f"- **Decision threshold:** {chosen['threshold']:.2f}",
            f"- **Input features:** {features[domain]}",
            f"- **Size on disk:** {chosen['size_mb']:.2f} MB "
            f"(limit {MAX_MODEL_MB:.0f} MB)",
            f"- **Latency on this PC:** {chosen['latency']['median_ms']:.3f} ms median "
            f"(limit {MAX_LATENCY_MS:.0f} ms)",
            f"- **Constraints:** {met}",
            "",
            "## Performance (test split, reported once)",
            "",
            f"- Accuracy: {test['accuracy']:.4f}",
            f"- Precision: {test['precision']:.4f}",
            f"- Recall: {test['recall']:.4f}",
            f"- F1: {test['f1']:.4f}",
            f"- False-negative rate (missed threats): "
            f"{test['false_negative_rate']:.4f}",
            f"- Confusion matrix (TN / FP / FN / TP): "
            f"{test['tn']} / {test['fp']} / {test['fn']} / {test['tp']}",
            "",
            "## Limitations",
            "",
            "- Scores come from one fixed split and one seed (no cross-validation).",
            "- Latency is measured on a PC, not on the target Arm phone.",
            "- Public datasets are older than today's threats.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the threat detectors.")
    parser.add_argument("--domain", choices=sorted(DOMAINS), action="append")
    args = parser.parse_args(argv)
    domains = args.domain or sorted(DOMAINS)
    try:
        records = [run_domain(domain) for domain in domains]
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}. Run the Phase 2 data pipeline first.", file=sys.stderr)
        return 1
    if len(domains) == len(DOMAINS):
        write_docs(records)
        print("[docs ] docs/model_comparison.md and docs/model_cards/ written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
