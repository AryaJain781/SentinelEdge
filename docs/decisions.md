# Architecture Decision Records (ADR)

Each decision is recorded once, with its context and consequences.
New decisions get the next number. Never delete an old record; mark it
"Superseded by ADR-XXXX" instead.

---

## ADR-0001: Two-stage design (classical ML detector + LLM explainer)

- **Status:** Accepted (2026-11-05)
- **Context:** Phones have limited battery, memory and compute. Running a
  large language model on every network event is too slow and too heavy.
- **Decision:** Small scikit-learn models flag threats in under 15 ms. Only
  flagged events are passed to a 4-bit quantised Llama 3.2 1B model, which
  writes a plain-English explanation.
- **Consequences:** Fast, low-power detection for every event. The LLM runs
  only on the small number of alerts, so its cost is paid rarely.

## ADR-0002: 100% offline at runtime (no cloud API calls)

- **Status:** Accepted (2026-11-05)
- **Context:** Security data is sensitive. Cloud services add latency,
  per-call cost and a privacy risk. Devices may also be air-gapped.
- **Decision:** All inference runs on the device. No network call is made
  during detection or explanation.
- **Consequences:** Strong privacy, zero running cost and resilience when
  offline. Model size and quality are limited by phone hardware.

## ADR-0003: Pinned Python 3.11 / 3.12 with pinned ML libraries

- **Status:** Accepted (2026-11-05)
- **Context:** Team members need identical results. numpy 1.26.4 does not
  support Python 3.13.
- **Decision:** `requires-python = ">=3.11,<3.13"`. Exact versions:
  scikit-learn 1.4.2, numpy 1.26.4, pandas 2.2.2, joblib 1.3.2. Dev tools:
  black 24.4.2, ruff 0.4.4, pytest 8.2.0.
- **Consequences:** Reproducible builds. Upgrades must be deliberate and
  recorded as a new ADR.

## ADR-0004: Source layout with `src/` package and Pytest `pythonpath`

- **Status:** Accepted (2026-11-05)
- **Context:** Imports must work the same in tests, scripts and the app.
- **Decision:** Code lives in `src/` as a package. `pyproject.toml` sets
  `pythonpath = ["."]` so tests import `src.<module>`.
- **Consequences:** No `sys.path` hacks. Clear separation from data,
  models and notebooks.

## ADR-0005: One-click check scripts (`check.ps1` and `check.bat`)

- **Status:** Accepted (2026-11-05)
- **Context:** Team members use both PowerShell and CMD. Quality checks
  must be run the same way every time.
- **Decision:** Both scripts run, in order: Black format, Ruff lint with
  auto-fix, Ruff lint (must be clean), then Pytest. They stop at the first
  failure.
- **Consequences:** One command gives a clear pass or fail result.
