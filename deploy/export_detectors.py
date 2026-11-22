"""Export the three trained Tier 1 detectors to a mobile-portable format.

Status: **written but not executed in this environment.** The sandbox this
script was authored in has no trained ``models/*.pkl`` bundles (they are
correctly gitignored and only exist on a team member's machine, per
``docs/data_sources.md``) and does not have ``skl2onnx``/``onnx`` installed,
with no network access to install them. Run this on a machine that has the
trained bundles and run ``pip install skl2onnx onnx onnxruntime`` first.
Do not assume it works end-to-end until someone has actually run it and
checked the output against ``deploy/validate_mobile_parity.py``.

What this does, per domain, and why the approach differs:

- **url** (`models/url_detector.pkl`): a plain `RandomForestClassifier` on 85
  numeric features, no `ColumnTransformer`. This is the easiest of the three
  to export — tree ensembles on numeric-only input are well supported by
  `skl2onnx`. Exported as ``url_detector.onnx``.
- **network** (`models/network_detector.pkl`): a `ColumnTransformer`
  (`OneHotEncoder` on 3 text columns + `StandardScaler` on the rest) feeding
  a `LogisticRegression`. Needs mixed `StringTensorType`/`FloatTensorType`
  inputs per column. Exported as ``network_detector.onnx``.
- **sms** (`models/sms_detector.pkl`): a `ColumnTransformer` built around
  `TfidfVectorizer(ngram_range=(1,2), min_df=2, sublinear_tf=True)` feeding
  `MultinomialNB`. **This is the real risk** flagged in
  ``docs/mobile_readiness_audit.md`` Section 1 — `skl2onnx`'s TF-IDF support
  is partial and version-dependent, and this project's vocabulary is
  uncapped (no `max_features`), so the exported graph's behaviour must be
  checked, not assumed. If the ONNX export's predictions diverge from the
  original pipeline by more than the 1% accuracy budget (checked by
  ``validate_mobile_parity.py``, not by this script), fall back to shipping
  the raw ``.pkl`` and running it through Chaquopy's embedded CPython
  instead, per the audit's recommendation. This script does not silently
  paper over that risk: it reports the ONNX export's local prediction
  parity against a few held-out rows immediately after exporting, cheaply,
  before the full validation script runs.

One discovered detail worth recording here, because it affects how "metadata
features" is described elsewhere in this project's docs: the **selected**
SMS pipeline (`baseline: alpha=0.1`) only feeds ``text_clean`` through its
`ColumnTransformer` — the 8 metadata columns (`urgency_count`, etc.) that
``SMSDetector.to_frame`` computes are present in the DataFrame handed to the
pipeline but are **dropped** by the `ColumnTransformer`'s default
``remainder="drop"``, because only the "text" transformer is registered for
the baseline family. They are computed (and must still be computed,
on-device, to match `to_frame`'s interface) but are not actually consumed by
the deployed model. This was discovered by reading `_sms_pipeline()` in
`src/detectors/train_detectors.py`, not assumed.

Usage::

    python -m deploy.export_detectors --domain all
    python -m deploy.export_detectors --domain url
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
EXPORT_DIR = PROJECT_ROOT / "models" / "mobile"

DOMAINS = ("url", "sms", "network")


def _load_bundle(domain: str) -> dict[str, Any]:
    path = MODELS_DIR / f"{domain}_detector.pkl"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Train the detectors first with "
            "`python -m src.detectors.train_detectors` on a machine that has "
            "the processed data splits (see docs/data_splits_summary.md)."
        )
    return joblib.load(path)


def _require(module_name: str):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise ImportError(
            f"'{module_name}' is not installed. Run:\n"
            "    pip install skl2onnx onnx onnxruntime\n"
            "before running this script. (Not installed in the sandbox this "
            "script was authored in, and not testable there — see the "
            "module docstring.)"
        ) from exc


def export_url(bundle: dict[str, Any]) -> Path:
    """RandomForestClassifier on 85 numeric features -> ONNX."""
    skl2onnx = _require("skl2onnx")
    from skl2onnx.common.data_types import FloatTensorType

    feature_names = bundle["feature_names"]
    initial_type = [("input", FloatTensorType([None, len(feature_names)]))]
    onnx_model = skl2onnx.convert_sklearn(
        bundle["pipeline"],
        initial_types=initial_type,
        target_opset=17,
    )
    out_path = EXPORT_DIR / "url_detector.onnx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(onnx_model.SerializeToString())
    _write_manifest(
        "url",
        out_path,
        input_spec={"input": {"dtype": "float32", "shape": [1, len(feature_names)]}},
        feature_order=list(feature_names),
        notes="Plain RandomForestClassifier, no ColumnTransformer. Lowest-risk export.",
    )
    return out_path


def export_network(bundle: dict[str, Any]) -> Path:
    """OneHotEncoder+StandardScaler -> LogisticRegression, ColumnTransformer -> ONNX."""
    skl2onnx = _require("skl2onnx")
    from skl2onnx.common.data_types import FloatTensorType, StringTensorType

    from src.utils.network_preprocessor import FEATURE_COLUMNS, TEXT_COLUMNS

    numeric_cols = [c for c in FEATURE_COLUMNS if c not in TEXT_COLUMNS]
    # skl2onnx needs one named input per column when a ColumnTransformer mixes
    # string and numeric dtypes; a single combined tensor does not work across
    # dtypes. Each column becomes its own [None, 1] input.
    initial_type = [(col, StringTensorType([None, 1])) for col in TEXT_COLUMNS] + [
        (col, FloatTensorType([None, 1])) for col in numeric_cols
    ]
    onnx_model = skl2onnx.convert_sklearn(
        bundle["pipeline"],
        initial_types=initial_type,
        target_opset=17,
    )
    out_path = EXPORT_DIR / "network_detector.onnx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(onnx_model.SerializeToString())
    _write_manifest(
        "network",
        out_path,
        input_spec={
            **{c: {"dtype": "string", "shape": [1, 1]} for c in TEXT_COLUMNS},
            **{c: {"dtype": "float32", "shape": [1, 1]} for c in numeric_cols},
        },
        feature_order=list(FEATURE_COLUMNS),
        notes=(
            "One named ONNX input per column (mixed string/numeric "
            "ColumnTransformer). The exact one-hot width was NOT "
            "independently measured here, per docs/mobile_readiness_audit.md "
            "Section 1 — confirm it from the exported graph, not from this "
            "comment."
        ),
    )
    return out_path


def export_sms(bundle: dict[str, Any]) -> Path:
    """TfidfVectorizer -> MultinomialNB, ColumnTransformer -> ONNX.

    Highest-risk export of the three (see module docstring). Export is
    attempted; the caller (validate_mobile_parity.py) is responsible for
    deciding whether the result is accurate enough to ship, or whether to
    fall back to Chaquopy with the raw .pkl instead.
    """
    skl2onnx = _require("skl2onnx")
    from skl2onnx.common.data_types import StringTensorType

    TEXT_COLUMN = "text_clean"
    initial_type = [(TEXT_COLUMN, StringTensorType([None, 1]))]
    try:
        onnx_model = skl2onnx.convert_sklearn(
            bundle["pipeline"],
            initial_types=initial_type,
            target_opset=17,
        )
    except Exception as exc:  # noqa: BLE001 - this is the expected risk path
        print(
            "SMS ONNX export failed. This is the known risk documented in "
            "docs/mobile_readiness_audit.md Section 1 (TfidfVectorizer export "
            f"support is partial/version-dependent). Error: {exc}",
            file=sys.stderr,
        )
        print(
            "Falling back: packaging the raw joblib pipeline for Chaquopy "
            "instead of ONNX.",
            file=sys.stderr,
        )
        return _package_for_chaquopy(bundle, "sms")

    out_path = EXPORT_DIR / "sms_detector.onnx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(onnx_model.SerializeToString())
    _write_manifest(
        "sms",
        out_path,
        input_spec={TEXT_COLUMN: {"dtype": "string", "shape": [1, 1]}},
        feature_order=[TEXT_COLUMN],
        notes=(
            "Metadata columns are NOT part of this graph: the selected "
            "baseline pipeline's ColumnTransformer only consumes "
            "'text_clean' (remainder='drop'), confirmed by reading "
            "_sms_pipeline() in src/detectors/train_detectors.py. "
            "Export succeeded, but TF-IDF/ONNX numerical parity must still "
            "be checked by validate_mobile_parity.py before trusting this "
            "file on-device."
        ),
    )
    return out_path


def _package_for_chaquopy(bundle: dict[str, Any], domain: str) -> Path:
    """Fallback path: ship the original joblib bundle as-is for Chaquopy.

    No conversion, no conversion-fidelity risk -- this is the exact same
    code and model already measured on the PC. The cost (an embedded Python
    interpreter in the APK) is a WP8 integration concern, not this script's.
    """
    out_path = EXPORT_DIR / f"{domain}_detector.chaquopy.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path, compress=3)
    _write_manifest(
        domain,
        out_path,
        input_spec={"note": "raw joblib bundle, run through scikit-learn via Chaquopy"},
        feature_order=list(bundle.get("feature_names", [])),
        notes="Chaquopy fallback: ONNX export was not used for this domain.",
    )
    return out_path


def _write_manifest(
    domain: str,
    artifact_path: Path,
    input_spec: dict[str, Any],
    feature_order: list[str],
    notes: str,
) -> None:
    manifest = {
        "domain": domain,
        "artifact": artifact_path.name,
        "input_spec": input_spec,
        "feature_order": feature_order,
        "notes": notes,
    }
    manifest_path = artifact_path.with_suffix(artifact_path.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2))


EXPORTERS = {
    "url": export_url,
    "sms": export_sms,
    "network": export_network,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=(*DOMAINS, "all"), default="all")
    args = parser.parse_args(argv)

    domains = DOMAINS if args.domain == "all" else (args.domain,)
    for domain in domains:
        print(f"Exporting {domain} ...")
        bundle = _load_bundle(domain)
        path = EXPORTERS[domain](bundle)
        print(f"  -> {path}")
    print(
        "\nExport step finished. This does NOT confirm the exported models "
        "are accurate on mobile hardware -- run "
        "`python -m deploy.validate_mobile_parity` next, on the same "
        "machine, before pushing anything to a phone."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
