"""Tests for the data splits: schema, row counts, class balance and zero leakage.

Two kinds of test live here:

* Synthetic tests run on small generated tables, so they always run.
* Real-data tests check the processed CSVs written by ``data_loader``. They are
  skipped when the processed files have not been built yet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.utils import data_loader as dl
from src.utils.network_preprocessor import FEATURE_COLUMNS
from src.utils.url_features import FEATURE_NAMES as URL_FEATURES

EXPECTED_ROWS = {"sms": 5574, "url": 58645, "network": 125973}
PROCESSED = dl.PROCESSED_DIR


def _synthetic_frame(n: int = 1000, positive_rate: float = 0.3) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "feature_a": rng.normal(size=n),
            "feature_b": rng.integers(0, 10, size=n),
            dl.LABEL: (rng.random(n) < positive_rate).astype(int),
        }
    )
    frame.insert(0, dl.ROW_ID, range(n))
    return frame


# ---------------------------------------------------------------- synthetic


def test_split_sizes_are_80_10_10() -> None:
    splits = dl.split_stratified(_synthetic_frame(1000))
    assert len(splits.train) == 800
    assert len(splits.val) == 100
    assert len(splits.test) == 100


def test_split_has_zero_leakage_between_partitions() -> None:
    splits = dl.split_stratified(_synthetic_frame(1000))
    train_ids = set(splits.train[dl.ROW_ID])
    val_ids = set(splits.val[dl.ROW_ID])
    test_ids = set(splits.test[dl.ROW_ID])
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)


def test_split_covers_every_row_exactly_once() -> None:
    frame = _synthetic_frame(1000)
    splits = dl.split_stratified(frame)
    combined = pd.concat([splits.train, splits.val, splits.test])
    assert len(combined) == len(frame)
    assert sorted(combined[dl.ROW_ID].tolist()) == sorted(frame[dl.ROW_ID].tolist())


def test_split_keeps_class_balance() -> None:
    frame = _synthetic_frame(2000, positive_rate=0.3)
    overall = frame[dl.LABEL].mean()
    splits = dl.split_stratified(frame)
    for part in (splits.train, splits.val, splits.test):
        assert abs(part[dl.LABEL].mean() - overall) < 0.02


def test_split_is_reproducible_with_locked_seed() -> None:
    frame = _synthetic_frame(500)
    first = dl.split_stratified(frame)
    second = dl.split_stratified(frame)
    pd.testing.assert_frame_equal(first.test, second.test)
    pd.testing.assert_frame_equal(first.train, second.train)


def test_seed_is_locked_to_42() -> None:
    assert dl.SEED == 42


def test_split_requires_row_id() -> None:
    frame = _synthetic_frame(100).drop(columns=[dl.ROW_ID])
    with pytest.raises(dl.DataLoaderError):
        dl.split_stratified(frame)


# ------------------------------------------------------------- real data


def _read_split(
    domain: str, name: str, columns: list[str] | None = None
) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / domain / f"{name}.csv", usecols=columns)


def _processed_ready(domain: str) -> bool:
    return all((PROCESSED / domain / f"{n}.csv").exists() for n in dl.SPLIT_NAMES)


needs_sms = pytest.mark.skipif(
    not _processed_ready("sms"), reason="sms split not built"
)
needs_url = pytest.mark.skipif(
    not _processed_ready("url"), reason="url split not built"
)
needs_network = pytest.mark.skipif(
    not _processed_ready("network"), reason="network split not built"
)


@needs_sms
def test_sms_schema_and_row_count() -> None:
    frames = [_read_split("sms", n) for n in dl.SPLIT_NAMES]
    assert sum(len(f) for f in frames) == EXPECTED_ROWS["sms"]
    header = _read_split("sms", "train").columns.tolist()
    assert "text_clean" in header
    assert dl.LABEL in header
    assert dl.ROW_ID in header


@needs_url
def test_url_schema_and_row_count() -> None:
    frames = [_read_split("url", n) for n in dl.SPLIT_NAMES]
    assert sum(len(f) for f in frames) == EXPECTED_ROWS["url"]
    header = _read_split("url", "train").columns.tolist()
    # 85 URL-only features plus row_id and label
    assert len(header) == 85 + 2
    assert not set(dl.MENDELEY_NETWORK_OR_WEB) & set(header)
    assert not set(dl.MENDELEY_CONSTANT) & set(header)


@needs_network
def test_network_schema_and_row_count() -> None:
    frames = [_read_split("network", n) for n in dl.SPLIT_NAMES]
    assert sum(len(f) for f in frames) == EXPECTED_ROWS["network"]
    header = _read_split("network", "train").columns.tolist()
    for column in FEATURE_COLUMNS:
        assert column in header
    assert {dl.LABEL, "attack_category", "difficulty", dl.ROW_ID} <= set(header)


@pytest.mark.parametrize("domain", ["sms", "url", "network"])
def test_real_splits_have_zero_leakage(domain: str) -> None:
    if not _processed_ready(domain):
        pytest.skip(f"{domain} split not built")
    ids = {
        name: set(_read_split(domain, name, [dl.ROW_ID])[dl.ROW_ID])
        for name in dl.SPLIT_NAMES
    }
    assert ids["train"].isdisjoint(ids["val"])
    assert ids["train"].isdisjoint(ids["test"])
    assert ids["val"].isdisjoint(ids["test"])
    total = sum(len(s) for s in ids.values())
    assert total == EXPECTED_ROWS[domain]
    assert set().union(*ids.values()) == set(range(EXPECTED_ROWS[domain]))


@pytest.mark.parametrize("domain", ["sms", "url", "network"])
def test_real_split_ratios_are_80_10_10(domain: str) -> None:
    if not _processed_ready(domain):
        pytest.skip(f"{domain} split not built")
    total = EXPECTED_ROWS[domain]
    sizes = {
        name: len(_read_split(domain, name, [dl.ROW_ID])) for name in dl.SPLIT_NAMES
    }
    assert abs(sizes["train"] / total - 0.80) < 0.001
    assert abs(sizes["val"] / total - 0.10) < 0.001
    assert abs(sizes["test"] / total - 0.10) < 0.001


def test_url_feature_count_matches_spec() -> None:
    assert len(URL_FEATURES) == 18


def test_processed_dir_is_git_ignored() -> None:
    root = Path(dl.PROJECT_ROOT)
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "data/processed/*" in gitignore
    assert "data/raw/*" in gitignore
