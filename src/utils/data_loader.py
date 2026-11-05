"""Build the processed train / validation / test splits for each threat domain.

Every split is 80% train, 10% validation and 10% test. Splits are stratified
on the binary label (so each part keeps the same class balance) and use the
locked random seed ``SEED = 42``. Each row gets a stable ``row_id`` before
splitting, so tests can prove that no row appears in two splits.

The 10% test split is written once and must be used only for the final
evaluation. Development work should use train and validation only.

Run from the project root::

    python -m src.utils.data_loader
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.utils.network_preprocessor import parse_nsl_kdd
from src.utils.sms_preprocessor import clean_sms, extract_sms_metadata

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SEED = 42
TRAIN_FRACTION = 0.80
VAL_FRACTION = 0.10
TEST_FRACTION = 0.10
SPLIT_NAMES: tuple[str, ...] = ("train", "val", "test")

ROW_ID = "row_id"
LABEL = "label"


class DataLoaderError(RuntimeError):
    """Raised when a raw dataset is missing or has an unexpected layout."""


@dataclass(frozen=True)
class Splits:
    """The three partitions of one domain."""

    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame

    def as_dict(self) -> dict[str, pd.DataFrame]:
        return {"train": self.train, "val": self.val, "test": self.test}


def split_stratified(
    frame: pd.DataFrame, label_column: str = LABEL, seed: int = SEED
) -> Splits:
    """Split ``frame`` 80/10/10 into train, validation and test.

    The split is stratified on ``label_column``.

    Steps: hold out 20%, then split that 20% in half. The result is exact to
    within one row because of rounding in the stratified split.
    """
    if ROW_ID not in frame.columns:
        raise DataLoaderError(
            f"Frame must contain a '{ROW_ID}' column before splitting"
        )
    if not math.isclose(TRAIN_FRACTION + VAL_FRACTION + TEST_FRACTION, 1.0):
        raise DataLoaderError("Split fractions must add up to 1.0")

    holdout_fraction = VAL_FRACTION + TEST_FRACTION
    train, holdout = train_test_split(
        frame,
        test_size=holdout_fraction,
        stratify=frame[label_column],
        random_state=seed,
        shuffle=True,
    )
    val, test = train_test_split(
        holdout,
        test_size=TEST_FRACTION / holdout_fraction,
        stratify=holdout[label_column],
        random_state=seed,
        shuffle=True,
    )
    return Splits(
        train=train.reset_index(drop=True),
        val=val.reset_index(drop=True),
        test=test.reset_index(drop=True),
    )


def _with_row_id(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.reset_index(drop=True)
    out.insert(0, ROW_ID, range(len(out)))
    return out


def _require(path: Path, hint: str) -> Path:
    if not path.exists():
        raise DataLoaderError(f"Missing raw file {path}. {hint}")
    return path


def load_sms_frame(raw_path: Path | None = None) -> pd.DataFrame:
    """Read the UCI SMS file and return cleaned text plus metadata and label."""
    path = _require(
        raw_path or RAW_DIR / "sms_uci" / "SMSSpamCollection",
        "Run: python -m src.utils.download_data",
    )
    raw = pd.read_csv(
        path, sep="\t", header=None, names=["class", "text"], quoting=3, dtype=str
    )
    raw = raw.dropna(subset=["class", "text"])
    labels = raw["class"].str.strip().str.lower()
    if not set(labels.unique()) <= {"spam", "ham"}:
        raise DataLoaderError(f"Unexpected SMS labels: {sorted(labels.unique())}")

    rows = []
    for text in raw["text"]:
        rows.append({"text_clean": clean_sms(text), **extract_sms_metadata(text)})
    frame = pd.DataFrame(rows)
    frame[LABEL] = (labels == "spam").astype(int).to_numpy()
    return _with_row_id(frame)


# The Mendeley file has 111 features. Columns 0-96 and column 110 are computed
# from the URL string; columns 97-109 need DNS, WHOIS, TLS or web lookups and are
# dropped (ADR-0007). Columns that are constant in the file are also dropped.
MENDELEY_NETWORK_OR_WEB = (
    "time_response",
    "domain_spf",
    "asn_ip",
    "time_domain_activation",
    "time_domain_expiration",
    "qty_ip_resolved",
    "qty_nameservers",
    "qty_mx_servers",
    "ttl_hostname",
    "tls_ssl_certificate",
    "qty_redirects",
    "url_google_index",
    "domain_google_index",
)
MENDELEY_CONSTANT = (
    "qty_slash_domain",
    "qty_questionmark_domain",
    "qty_equal_domain",
    "qty_and_domain",
    "qty_exclamation_domain",
    "qty_space_domain",
    "qty_tilde_domain",
    "qty_comma_domain",
    "qty_plus_domain",
    "qty_asterisk_domain",
    "qty_hashtag_domain",
    "qty_dollar_domain",
    "qty_percent_domain",
)
MENDELEY_LABEL = "phishing"


def load_url_frame(raw_path: Path | None = None) -> pd.DataFrame:
    """Read the Mendeley phishing CSV and keep the URL-only features (85 columns)."""
    path = _require(
        raw_path or RAW_DIR / "phishing_mendeley" / "dataset_small.csv",
        "Run: python -m src.utils.download_data",
    )
    raw = pd.read_csv(path)
    if MENDELEY_LABEL not in raw.columns:
        raise DataLoaderError(f"Label column '{MENDELEY_LABEL}' not found in {path}")
    drop = set(MENDELEY_NETWORK_OR_WEB) | set(MENDELEY_CONSTANT)
    keep = [c for c in raw.columns if c not in drop and c != MENDELEY_LABEL]
    frame = raw[keep].copy()
    frame[LABEL] = raw[MENDELEY_LABEL].astype(int).to_numpy()
    return _with_row_id(frame)


def load_network_frame(raw_path: Path | None = None) -> pd.DataFrame:
    """Read the NSL-KDD training file: 41 features, binary label, category."""
    path = _require(
        raw_path or RAW_DIR / "nsl_kdd" / "KDDTrain+.txt",
        "Run: python -m src.utils.download_data",
    )
    return _with_row_id(parse_nsl_kdd(path))


DOMAIN_LOADERS = {
    "sms": load_sms_frame,
    "url": load_url_frame,
    "network": load_network_frame,
}


def build_domain(domain: str, out_dir: Path | None = None) -> Splits:
    """Load one domain, split it, and write train/val/test CSVs."""
    if domain not in DOMAIN_LOADERS:
        raise DataLoaderError(f"Unknown domain '{domain}'")
    frame = DOMAIN_LOADERS[domain]()
    splits = split_stratified(frame)
    target = out_dir or PROCESSED_DIR / domain
    target.mkdir(parents=True, exist_ok=True)
    for name, part in splits.as_dict().items():
        part.to_csv(target / f"{name}.csv", index=False)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build processed splits.")
    parser.add_argument(
        "--domain",
        choices=sorted(DOMAIN_LOADERS),
        action="append",
        help="domain to build (repeatable); default: all",
    )
    args = parser.parse_args(argv)
    domains = args.domain or sorted(DOMAIN_LOADERS)
    try:
        for domain in domains:
            splits = build_domain(domain)
            sizes = {name: len(part) for name, part in splits.as_dict().items()}
            print(f"[ok] {domain}: {sizes}")
    except DataLoaderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
