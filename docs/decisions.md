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

---

## ADR-0006: Three threat vectors for the detectors

- **Status:** Accepted (2026-11-05, Phase 1)
- **Context:** The project needs a focused scope that can be built and
  evaluated within the M.Tech timeline.
- **Decision:** Build three micro-detectors: phishing URLs, scam SMS, and
  network-flow anomalies. Each has its own dataset and its own documentation
  in `docs/threat_explainers.md`.
- **Consequences:** Clear, testable scope. Each detector has its own
  false-positive and false-negative analysis. Other threats are out of scope
  unless a new ADR adds them.

## ADR-0007: Runtime detection uses static, offline features only

- **Status:** Accepted (2026-11-05, Phase 1)
- **Context:** Visiting a suspicious link or contacting a server would leak
  data and break the offline rule (ADR-0002).
- **Decision:** At runtime, every feature is computed from the item itself
  (URL string, SMS text, or flow record). No page is fetched and no lookup
  service is called. Any dataset column that needs a web visit is excluded
  from the runtime feature set.
- **Consequences:** Safe and private, and it fits the offline rule. Some
  threats, such as a new phishing page on a hacked real domain, cannot be
  caught this way, and the report must say so.

## ADR-0008: The detector decides, the language model only explains

- **Status:** Accepted (2026-11-05, Phase 1)
- **Context:** A language model can be tricked by hostile text (prompt
  injection), so it should not make security decisions.
- **Decision:** The block-or-allow decision comes from the classical detector
  score. The Llama model receives only the detector's clues and a delimited,
  sandboxed copy of the untrusted text, and it writes the explanation. The
  model has no tools and no network access.
- **Consequences:** A successful prompt injection can change the wording of
  the explanation but not the decision. The Delimited Prompt Shield is a
  required component (WP5).

## ADR-0009: 4-bit groupwise Llama 3.2 1B on ExecuTorch with XNNPACK

- **Status:** Accepted, with a memory risk (2026-11-05, Phase 1)
- **Context:** The model must run on an Arm Android CPU within a phone's RAM.
  Public 4-bit exports are about 1.0 GiB, which is larger than our 750 MB plan.
- **Decision:** Use ExecuTorch with the XNNPACK backend and 4-bit groupwise
  weights. Set a peak-memory budget of under 1.1 GB, with a 2,048-token
  context as the default. If measured memory exceeds the budget, reduce the
  context to 1,024 tokens first, then revisit quantization settings.
- **Consequences:** The budget is an estimate and must be measured in WP6.
  Any change to the context length or quantization becomes a new ADR.

## ADR-0010: Dataset licence must be confirmed before use

- **Status:** Accepted (2026-11-05, Phase 1)
- **Context:** Sources disagree or are silent on the licences of the UCI SMS
  Spam Collection, the Mendeley phishing dataset and NSL-KDD. Using data
  without permission is a legal and academic risk.
- **Decision:** No dataset is downloaded or used in code until its licence is
  confirmed on its official page and recorded in `docs/data_sources.md`.
- **Consequences:** WP1 includes a licence-check step. Phase 2 cannot start on
  a dataset that is still marked "Verify".

## ADR-0011: Phishing URL detector favours high recall

- **Status:** Accepted (2026-11-05, Phase 1)
- **Context:** Missing a phishing site can expose passwords and card details,
  which is more harmful than a false alarm that the user can dismiss.
- **Decision:** Choose the URL detector threshold to favour recall. Each block
  shows its reasons and an easy "I trust this site" option. The final threshold
  will be set in WP2 using the validation data.
- **Consequences:** Some legitimate unusual domains will be flagged. Precision
  is reported alongside recall in the benchmark phase.

## ADR-0012: URL detector trains on the 85 precomputed Mendeley features

- **Status:** Accepted (2026-11-05, Phase 2, team decision: option A)
- **Context:** The Mendeley dataset contains precomputed numbers but no raw web
  addresses. The 18-clue extractor in `src/utils/url_features.py` needs raw
  addresses, so it cannot be trained on this data.
- **Decision:** Train the URL detector (WP2) on the 85 URL-only columns that
  `src/utils/data_loader.py` keeps from the Mendeley file. The 18-clue
  extractor is kept as a readable, explainable utility and is used for
  explanations and demonstrations, not as training input.
- **Consequences:** The URL detector can be built now without finding a new
  dataset. The report must state that the 18-clue extractor was not used for
  training, and that the trained features are the dataset's 85 columns. A
  future phase could add a raw-URL dataset as a new decision.

## ADR-0013: NSL-KDD "worm" attacks are grouped under DoS

- **Status:** Accepted (2026-11-05, Phase 2, team decision)
- **Context:** NSL-KDD does not name a category for the `worm` attack. Papers
  group it differently: some put it under DoS, others under a separate group.
- **Decision:** Keep `worm` in the DoS category, as the mapping in
  `src/utils/network_preprocessor.py` already does. The report must state this
  choice. The category mapping is part of the code, so any change needs a new
  ADR.
- **Consequences:** The DoS count in the training split includes worm records.
  Results for the DoS family must be read with this in mind.

## ADR-0014: Model selection protocol (Phase 3)

- **Status:** Accepted (2026-11-05, Phase 3)
- **Context:** Choosing a model by looking at the test set would make the
  reported scores optimistic.
- **Decision:** Fit each candidate on the train split only. Tune hyperparameters
  and the URL threshold on the validation split. Pick the best validation F1
  among candidates that meet the limits (model file under 25 MB and median
  prediction under 15 ms on this PC). Score the test split once, for reporting.
  If no candidate meets the limits, the best validation F1 is used and flagged.
- **Consequences:** The reported test scores are not inflated by selection.
  In NSL-KDD, the random forest has the higher test F1 but misses the latency
  limit by about 1 ms on this PC, so the logistic regression is chosen. In SMS,
  the naive Bayes model is chosen on validation F1, even though the logistic
  regression scores higher on test. We report both and do not switch after
  seeing test results.

## ADR-0015: Single-thread prediction for one-sample inference

- **Status:** Accepted (2026-11-05, Phase 3)
- **Context:** Random forests trained with all CPU cores were 41 ms per single
  prediction, because thread start-up dominates for one sample.
- **Decision:** Train with all cores, then set the forest to one thread before
  saving it for prediction.
- **Consequences:** The URL forest drops from 41 ms to about 13 ms per sample.
  Batch prediction will be slower per row; this is acceptable for a detector
  that scores one event at a time.

## ADR-0017: URL forest uses 50 trees (Phase 5)

- **Status:** Accepted (2026-11-05, Phase 5)
- **Context:** The 100-tree URL forest had a median prediction time of about
  14 ms on this PC, and its 95th percentile went above the 15 ms limit, so the
  speed test was unreliable.
- **Decision:** Use 50 trees for the URL forest. The choice was made from the
  latency measurement, not from test scores. Depth is still chosen on validation.
- **Consequences:** The URL model is faster and smaller. Its scores were
  re-measured on the test split, and the report must say that the URL model
  changed in Phase 5. The 85 features and the threshold rule are unchanged.

## ADR-0018: Test split status and what counts as a fresh test (Phase 5)

- **Status:** Accepted (2026-11-05, Phase 5)
- **Context:** The Phase 5 brief expected the test split to be opened for the
  first time. It had already been scored once in Phase 3, for the model report.
- **Decision:** Do not describe the Phase 5 run as the first look at the test
  split. Every report says the test split was used in Phase 3. A genuinely
  unseen test needs new data, collected or downloaded after this point, and must
  be scored once with the final models unchanged.
- **Consequences:** The reported scores are a final check on the same split, not
  independent evidence. The limit is stated in the guide, the progress report and
  the benchmark summary.

## ADR-0016: Explainer cannot change the verdict; prompt-injection defences (Phase 4)

- **Status:** Accepted (2026-11-05, Phase 4)
- **Context:** SMS and URL text is written by attackers. A language model that
  reads it as instructions could be made to call a scam safe.
- **Decision:** (1) The detector sets the verdict; the language model only
  writes the explanation. (2) Untrusted text sits between the markers
  `### BEGIN UNTRUSTED DATA ###` and `### END UNTRUSTED DATA ###`, after marker
  look-alikes and control characters are removed and the length is capped.
  (3) The system prompt treats the block as inert data. (4) Every advisory is
  checked for the three numbered steps, for marker repetition and for "safe"
  claims about a threat. Failed checks use a fixed template instead. (5) The
  template runner never reads the untrusted text.
- **Consequences:** An injected instruction can at most change wording, and it
  is discarded if it breaks the format. These defences reduce the risk; they do
  not remove it, and the report must say so. The Llama runner is a stub until
  Phase 6, so the explanations shown now come from the template.
- **Known gap:** raw web addresses are reported as unsupported, because the URL
  model needs the 85 Mendeley columns, which this build does not compute.
