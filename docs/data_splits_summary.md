# Data Splits Summary (Phase 2)

This document records the exact sample counts and class balance of every
processed split. All numbers were produced by
`python -m src.utils.data_loader` on 2026-11-05, with the locked seed
`SEED = 42`.

**Split rule:** 80% train, 10% validation, 10% test. Each split is stratified
on the binary label, so every part keeps the same class balance as the whole
dataset. The 10% test split is for the final evaluation only.

**Leakage check:** each row has a stable `row_id`. The tests in
`tests/test_data_loaders.py` confirm that the three splits are disjoint and
together cover every row exactly once.

---

## 1. SMS spam (UCI SMS Spam Collection)

| Split | Rows | Spam (label 1) | Ham (label 0) | Spam share |
|---|---:|---:|---:|---:|
| Train | 4,459 | 598 | 3,861 | 13.41% |
| Validation | 557 | 74 | 483 | 13.29% |
| Test | 558 | 75 | 483 | 13.44% |
| **Total** | **5,574** | **747** | **4,827** | **13.40%** |

Columns: `row_id`, `text_clean`, 8 metadata columns (`urgency_count`,
`exclamation_count`, `uppercase_ratio`, `financial_count`, `has_url`,
`has_phone`, `has_currency`, `length_chars`), `label`. Total 11 columns.

## 2. Phishing URLs (Mendeley Phishing Websites Dataset, small variant)

| Split | Rows | Phishing (label 1) | Legitimate (label 0) | Phishing share |
|---|---:|---:|---:|---:|
| Train | 46,916 | 24,518 | 22,398 | 52.26% |
| Validation | 5,864 | 3,064 | 2,800 | 52.25% |
| Test | 5,865 | 3,065 | 2,800 | 52.26% |
| **Total** | **58,645** | **30,647** | **27,998** | **52.26%** |

Columns: `row_id`, 85 URL-only features, `label`. Total 87 columns.

**Feature choice:** the 111 Mendeley columns were reduced to 85 (see
`docs/data_sources.md`). The 13 network or web-lookup columns were dropped
(ADR-0007), and the 13 constant columns were dropped.

**Important:** this dataset does not contain the raw URL strings. The
18-feature URL extractor (`src/utils/url_features.py`) works on raw URLs, so it
cannot be applied to these rows. See the open decision in Section 5.

## 3. Network flows (NSL-KDD training file, team-approved)

| Split | Rows | Attack (label 1) | Normal (label 0) | Attack share |
|---|---:|---:|---:|---:|
| Train | 100,778 | 46,904 | 53,874 | 46.54% |
| Validation | 12,597 | 5,863 | 6,734 | 46.54% |
| Test | 12,598 | 5,863 | 6,735 | 46.54% |
| **Total** | **125,973** | **58,630** | **67,343** | **46.54%** |

Columns: `row_id`, 41 features (3 of them text: `protocol_type`, `service`,
`flag`), `label`, `attack_category`, `difficulty`. Total 45 columns.

**Attack categories in the training split:**

| Category | Train rows | Share of attacks |
|---|---:|---:|
| Normal | 53,874 | — |
| DoS | 36,822 | 78.5% of attacks |
| Probe | 9,267 | 19.8% of attacks |
| R2L | 769 | 1.6% of attacks |
| U2R | 46 | 0.1% of attacks |

**Imbalance warning:** R2L (769) and U2R (46) are very rare. A model may
ignore them unless we weight the classes or report per-category results.

The NSL-KDD **test file was not used**: it was rejected in Phase 1 because its
values were altered.

---

## 4. Summary

| Domain | Total rows | Train | Validation | Test | Positive share |
|---|---:|---:|---:|---:|---:|
| SMS spam | 5,574 | 4,459 | 557 | 558 | 13.40% |
| Phishing URL | 58,645 | 46,916 | 5,864 | 5,865 | 52.26% |
| Network attack | 125,973 | 100,778 | 12,597 | 12,598 | 46.54% |

## 5. Open decisions

1. **URL domain source: decided (ADR-0012).** The URL detector trains on the
   85 precomputed Mendeley features. The 18-clue extractor is a utility for
   explanations and demonstrations, not a training input.
2. **"worm" category.** NSL-KDD's `worm` attack is placed in DoS here. Some
   papers place it elsewhere. The report must state this choice.
