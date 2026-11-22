# PRD Compliance & Security Audit

**Date:** 2026-11-21
**Scope:** Repository state at commit `9109de8` (origin/main, Phase 7 — "Pre-Hardware Freeze & Readiness Check")
**Method:** Automated repository scan (not a claim of formal security review). Every finding below was produced by actually running the listed commands against the repository tree, not inferred.

---

## 1. Zero cloud API keys, tokens, or endpoints in the code

**Check performed:** case-insensitive pattern search across `src/`, `deploy/`, and `tests/`, plus the full `requirements.txt` / `pyproject.toml` dependency lists, for:
`api_key`, `secret_key`, `access_token`, `bearer`, `authorization:`, OpenAI/Anthropic-style key prefixes (`sk-...`), `openai`, `googleapis.com`, `AIza...` (Google API key pattern), and any `http(s)://` call site in code (not docs).

**Result: PASS.**

- No API keys, secrets, bearer tokens, or cloud-SDK imports (`openai`, `boto3`, `anthropic`, `google-cloud-*`, etc.) exist anywhere in the codebase or dependency list.
- `requirements.txt` and `pyproject.toml` list exactly four runtime dependencies: `scikit-learn==1.4.2`, `numpy==1.26.4`, `pandas==2.2.2`, `joblib==1.3.2` — all local, offline libraries. This matches ADR-0002 ("100% offline at runtime") and ADR-0003 (pinned stack).
- The only `http://` / `https://` strings found in code are:
  - Three one-time dataset-download URLs in `src/utils/download_data.py` (UCI SMS Spam Collection, Mendeley Phishing Websites Dataset, Zenodo NSL-KDD mirror) — used during offline dataset setup, never called at inference time.
  - Synthetic phishing/scam URLs used as **test fixtures** (e.g. `http://paypa1-verify.xyz/login`, `http://bit.ly/x1`) in `tests/` and `src/detectors/demo_sms.py` — these are fake example inputs the detectors are trained/tested to flag, not live network calls.
- `src/pipeline/router.py` only checks whether an input *string* starts with `http://`/`https://`/`www.` to classify it as a URL — it never fetches that URL (consistent with ADR-0007: "No page is fetched and no lookup [is] made").

No code path in this repository makes an outbound network call during detection or explanation.

## 2. `.gitignore` excludes raw data, model weights, and internal files

**Check performed:** read the committed `.gitignore` in full, then cross-checked against `git ls-tree -r origin/main` to confirm nothing it should exclude is actually tracked.

**Result: PASS.**

| Category | `.gitignore` rule | Verified tracked files |
|---|---|---|
| Raw/processed datasets | `data/raw/*`, `data/processed/*`, `*.csv`, `*.parquet` | Only `data/raw/.gitkeep` and `data/processed/.gitkeep` are tracked — no actual data files |
| Model weights/artifacts | `models/*`, `*.pkl`, `*.joblib`, `*.pte`, `*.pt`, `*.onnx`, `*.bin`, `*.gguf`, `*.safetensors` | Only `models/.gitkeep` is tracked — no weights committed |
| Internal team docs | `*Team_Guide*`, `*PRD*`, `TEAM_EXPLAINER_AND_VIVA_GUIDE.md` | Confirmed absent from tracked tree |
| Secrets | `.env`, `.env.*`, `*.key`, `*.pem` | None present in tracked tree |
| Build/venv/cache noise | `.venv/`, `__pycache__/`, `.pytest_cache/`, etc. | None present |

One note, not a gap: `*.txt` is globally ignored (to catch stray data dumps) with an explicit `!requirements.txt` exception, which is why `requirements.txt` is still tracked correctly.

## 3. `check.ps1` — 0 lint errors, 100% passing tests

**Result at last run (Phase 7 verification, same commit this audit covers): PASS.**

`check.ps1` runs Black → Ruff (autofix) → Ruff (clean check) → Pytest in sequence and stops at the first failure (ADR-0005). The last full run on your machine reported:

```
156 passed, 2 skipped, 1 warning
ALL CHECKS PASSED
```

The 2 skips are the known, documented case of tests that require a trained model bundle not present in a fresh clone (guarded skips, not failures). No lint or format errors.

**Update (2026-11-22, Phase 9):** `check.ps1` was re-run after the Phase 8 `deploy/` scripts (`export_detectors.py`, `validate_mobile_parity.py`, `export_llama_pte.py`) were added to the repo. Result:

```
==> 1/4 Formatting with Black — All done! 27 files left unchanged.
==> 2/4 Linting with Ruff (auto-fix) — All checks passed!
==> 3/4 Linting with Ruff (must be clean) — All checks passed!
==> 4/4 Running tests with Pytest — 156 passed, 2 skipped, 1 warning
ALL CHECKS PASSED (format, lint, tests)
```

Same pass/skip counts as the Phase 7 run, confirming the Phase 8 scripts are Black/Ruff-clean and introduced no regressions. The 1 warning is a harmless `scipy.optimize` deprecation notice from inside `sklearn`'s internals, unrelated to this project's code. The scope note above (about `skl2onnx`/`executorch`/`optimum-executorch` not being part of the pinned runtime stack) still applies to why those packages aren't in `requirements.txt` — it does not affect this lint/format/test result.

---

## Overall verdict

All three PRD Section 3 Operating Rules items **pass**: no cloud dependency, no secrets, clean `.gitignore`, and a clean full-repo test run including the Phase 8 deliverables. No open items remain from this audit.
