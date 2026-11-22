# SentinelEdge: On-Device Cyber Threat Detection with a Llama-Based Explainable Assistant

**Technical Report — Phases 0–5 (WP0–WP5)**
**Status note:** this report is written during Phase 6 (WP6), the documentation
phase. It describes what is built and measured as of this phase. The on-device
language model (ExecuTorch export of Llama 3.2 1B) is a **design plan, not yet
built**; every number about it below is marked *estimate*. See Section 8 and
the status table in Section 2 for exactly what is implemented versus planned.

Run date for all measured numbers: 2026-11-05. Seed: 42 throughout. Platform
for all measurements: development PC (see Section 7 for why phone numbers are
not yet available).

---

## Section 1: Problem & Motivation

Mobile devices are now a primary attack surface for three everyday threat
types: phishing delivered through links, scam ("smishing") delivered through
SMS text, and network-level intrusion against the device or the network it
sits on. A user can meet all three in the same week, often from the same
attacker infrastructure (a phishing link sent inside a scam SMS, backed by a
scanning or flooding campaign against the service it impersonates).

The conventional response to these threats is a cloud-backed API: the phone
sends the URL, the message, or the flow summary to a server, and the server
returns a verdict. This has three structural weaknesses for a phone-based
defender:

- **Latency and connectivity.** A round trip to a cloud API typically costs on
  the order of hundreds of milliseconds, and it fails outright with no signal,
  in flight mode, or in an air-gapped deployment. A threat that must be caught
  as the SMS arrives or the connection opens cannot wait on a network call
  that may not even complete.
- **Privacy.** Sending every URL a user taps, every SMS they receive, and a
  summary of their network traffic to a third party is itself a privacy
  exposure, independent of whether the service is trustworthy. This is data a
  user may not want to leave the device under any circumstances.
- **Running cost and availability.** A cloud API is a per-request cost and a
  single point of failure; if the vendor's service is down or the account
  lapses, the protection disappears.

SentinelEdge's premise (ADR-0001, ADR-0002) is that the detection step does
not need a large model: the static, structural signals that mark a phishing
URL, a scam SMS, or an anomalous network flow (see Section 3) can be captured
by small, classical machine-learning models that run in single-digit
milliseconds on commodity phone hardware, entirely offline. A large language
model is reserved for the much rarer job of turning a terse verdict into a
plain-English explanation the user can act on — and only for the small
fraction of events the micro-detectors actually flag.

---

## Section 2: System Architecture

SentinelEdge is a two-tier pipeline (ADR-0001):

**Tier 1 — micro-detectors (implemented, measured).** Three independent
classical ML models, one per threat vector (URL, SMS, network flow). Each
takes one event and returns a threat score in well under the project's 15 ms
latency budget (Section 4). All three load from a single unified entry point,
`src.pipeline.router.analyze()`, which detects the input type, calls the
matching detector, and returns a `Verdict` dataclass (status, label,
confidence, threat score, detector name, and the extracted clues).

**Tier 2 — explanation (partially implemented).** When Tier 1 flags an event,
the clues and verdict (never the raw untrusted text as "instructions") are
assembled into a prompt and passed to a language-model runner behind a single
`LLMRunner` interface (`src/explainer/runtime.py`). Two runners exist today:

- `TemplateRunner` — a deterministic, rule-based advisory keyed off the
  verdict label. It never reads the untrusted text, so it cannot be
  manipulated by it. This is what actually produces the advisories shown by
  the CLI and the benchmark today.
- `ExecuTorchRunner` — intended to run a 4-bit-quantised Llama 3.2 1B `.pte`
  file through the ExecuTorch runtime on-device. **This is a stub.** Its
  constructor raises `RunnerUnavailable` unconditionally, with the message
  "ExecuTorch generation is wired in Phase 6" (a label left over from the
  project's original work-package numbering, where "Phase 6" meant the
  ExecuTorch export step — see the note below). No `.pte` file has been
  exported and no device measurement exists yet.

Every advisory, from either runner, is passed through `validate_advisory()`
before being shown: it must contain exactly three numbered defensive steps,
must not repeat the untrusted-data markers, and — if the verdict is a threat —
must not contain a "this is safe" claim. An advisory that fails validation is
discarded in favour of the fixed template. This keeps the decision authority
with the detector even if the explainer malfunctions or is attacked (ADR-0008).

**A naming note the reader should have before Section 5 onward:** the
project's documentation uses "Phase 6" / "WP6" in two different senses that
must not be conflated:

1. In `docs/executorch_summary.md` and the `ExecuTorchRunner` stub, "Phase 6" /
   "WP6" refers to **building and measuring the on-device Llama export**
   (ADR-0009). That work has **not** started.
2. In this project's current prompt sequence, "Phase 6" refers to **this
   documentation and report-writing pass**, which covers Phases 0–5.

This report is written under sense (2). Sense (1)'s Llama/ExecuTorch work
remains fully in the planning stage described in Section 5, and is carried
forward as an open item, not claimed as done here.

### Implementation status by work package

| Work package | Scope | Status as of this report |
|---|---|---|
| WP0 | Project scaffolding, lint/format/test tooling | Done |
| WP1 | Dataset selection, licence review, threat modelling | Done |
| WP2 | URL micro-detector | Done — trained, measured (Section 4) |
| WP3 | SMS micro-detector | Done — trained, measured (Section 4) |
| WP4 | Network-flow micro-detector | Done — trained, measured (Section 4) |
| WP5 | Unified router + Delimited Prompt Shield | Done — implemented and tested (`src/pipeline/router.py`, `src/explainer/prompt_builder.py`) |
| WP6 (ExecuTorch sense) | Llama 3.2 1B 4-bit export to `.pte`, on-device measurement | **Not started.** Design budget only (Section 5) |
| WP6 (documentation sense) | This report and finalized README | In progress / delivered with this report |
| WP7–WP9 | Tier1→Tier2 integration polish, Android deployment, final benchmarks/viva | Not started (`deploy/` is an empty placeholder) |

---

## Section 3: Datasets & Feature Engineering

**A correction to the original brief:** this section's working title mentioned
"PhishTank/Tranco" as the URL data source. The team evaluated PhishTank and
Tranco during dataset selection and did **not** use either (`docs/
dataset_shortlist.md`): PhishTank was rejected because its terms were
restrictive and unconfirmed and because it is a live feed rather than a fixed,
reproducible benchmark; Tranco was set aside as an unverified, optional
supplement. The URL dataset actually used, trained on, and reported throughout
this document is the **Mendeley Phishing Websites Dataset** (Vrbančič, Fister
Jr. and Podgorelec, 2020). The numbers below reflect that actual decision, not
the original brief's wording.

### 3.1 Datasets, licensing and splits

All three datasets are licensed for this use and were downloaded with
checksum verification (`docs/data_sources.md`); none are committed to the
repository (`.gitignore` excludes `data/raw/`, `data/processed/`, and common
tabular formats). Every split below is an 80/10/10 stratified split on the
binary label, built once with a locked `SEED = 42`, with disjoint, exhaustive
`row_id` coverage verified by `tests/test_data_loaders.py`.

| Dataset | Used for | Licence | Total rows | Train / Val / Test | Positive share |
|---|---|---|---:|---|---:|
| UCI SMS Spam Collection | SMS detector (WP3) | CC BY 4.0 (confirmed on UCI page) | 5,574 | 4,459 / 557 / 558 | 13.40% |
| Mendeley Phishing Websites Dataset (small variant) | URL detector (WP2) | CC BY 4.0 (confirmed on Mendeley record) | 58,645 | 46,916 / 5,864 / 5,865 | 52.26% |
| NSL-KDD (`KDDTrain+.txt` only) | Network detector (WP4) | Redistribution/mirroring allowed with citation (CIC terms) | 125,973 | 100,778 / 12,597 / 12,598 | 46.54% |

Two dataset-specific decisions affect how these numbers should be read:

- **NSL-KDD test file rejected.** The official NSL-KDD test file
  (`KDDTest+.txt`) could not be obtained from the CIC page (discontinued), so
  a Zenodo mirror and a GitHub mirror were byte-compared. The Zenodo copy of
  the *training* file matched the GitHub copy value-for-value and was
  approved. The Zenodo copy of the *test* file differed from the GitHub copy
  in 306 rows' `service` column and was **rejected as altered**. Consequently
  all NSL-KDD splits above (train/val/test) are carved from the single
  approved training file, not from a separate official test file.
- **`worm` attacks classified under DoS** (ADR-0013), a documented,
  non-standard mapping choice that affects the DoS category's composition.

### 3.2 Feature engineering

**SMS (11 columns total):** `text_clean` (TF-IDF, 1–2 grams) plus 8 metadata
counts — `urgency_count`, `exclamation_count`, `uppercase_ratio`,
`financial_count`, `has_url`, `has_phone`, `has_currency`, `length_chars` —
directly encoding the urgency/OTP/reward social-engineering signals described
in `docs/threat_explainers.md`.

**URL (87 columns total):** the Mendeley dataset ships 111 precomputed
features. 13 were dropped as constant (no information), and 13 more were
dropped because they require a network lookup (DNS, WHOIS, TLS, or a search
index) and would violate the offline-only runtime rule (ADR-0007). This
leaves **85 URL-string-only features** — lengths and counts of URL/domain/
path/filename/parameter tokens, IP-in-host and shortener checks. A
**separate, 18-feature lexical/entropy extractor** (`src/utils/
url_features.py`, computing things like Shannon entropy and typosquat edit
distance from a raw URL string) exists in the codebase but is **not** the
training input for the URL detector — the Mendeley dataset contains no raw
URL strings to apply it to (ADR-0012). It is used only for human-readable
explanation clues and demonstrations. This is a deliberate, documented
distinction and should not be conflated in the report with the trained
feature set.

**Network (45 columns total):** the 41 standard NSL-KDD fields (38 numeric,
3 categorical — `protocol_type`, `service`, `flag` — one-hot encoded), plus
`label`, `attack_category` and `difficulty` retained as metadata, not model
inputs.

---

## Section 4: Detector Models & Measured Results

Model selection protocol (ADR-0014): each candidate was fit on the train
split only; hyperparameters and the URL decision threshold were tuned on the
validation split; the test split was scored exactly once, for reporting. The
selection rule was *best validation F1 among candidates meeting both hard
limits* (model file < 25 MB, median single-sample prediction < 15 ms on the
measurement PC). All models were re-scored once in Phase 5
(`benchmarks/evaluate_all.py`) against the same saved artifacts and
reproduced the Phase 3 numbers exactly (`docs/benchmark_summary.md`).

### Comparative results (test split, reported once; official benchmark run, 2026-11-05)

| Domain | Model (selected) | Accuracy | Precision | Recall | F1 | False-negative rate | Latency, median single-sample (ms) | Disk size (MB) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| URL phishing | Random forest, `max_depth=16`, 50 trees | 0.8194 | 0.7510 | 0.9791 | 0.8500 | 0.0209 | 9.03–9.11 | 1.12–1.18 |
| SMS scam | Multinomial Naive Bayes, `alpha=0.1` | 0.9857 | 0.9855 | 0.9067 | 0.9444 | 0.0933 | 3.94 | 0.51 |
| Network attack | Logistic regression, `C=1.0` | 0.9695 | 0.9768 | 0.9572 | 0.9669 | 0.0428 | 7.43–7.62 | 0.01 |

(URL latency/size figures show a small range because the model card and the
benchmark-summary document round to a different number of decimal places from
the same underlying run; both sources agree to within 0.1 ms and 0.06 MB.)

Confusion matrices (TN / FP / FN / TP), test split:

- URL: 1,805 / 995 / 64 / 3,001
- SMS: 482 / 1 / 7 / 68
- Network: 6,602 / 133 / 251 / 5,612

**Baseline vs. improved, side by side (validation-selected winner in bold):**

| Domain | Candidate | Val F1 | Test F1 | Test latency (ms) | Test size (MB) | Why this one was / wasn't selected |
|---|---|---:|---:|---:|---:|---|
| URL | baseline `C=1.0` (logistic regression) | 0.8335 | 0.8371 | 4.95 | 0.00 | Meets limits, lower F1 |
| URL | **improved `max_depth=16`** (random forest) | **0.8419** | 0.8500 | 9.11 | 1.12 | Selected: higher validation F1, meets both limits |
| SMS | **baseline `alpha=0.1`** (Naive Bayes) | **0.9577** | 0.9444 | 3.94 | 0.51 | Selected on validation F1, despite scoring lower than the alternative on test (ADR-0014 — decision locked before the test score was seen) |
| SMS | improved `C=10.0` (logistic regression) | 0.9306 | 0.9589 | 6.83 | 0.40 | Not selected; scored higher on test only in hindsight |
| Network | **baseline `C=1.0`** (logistic regression) | **0.9724** | 0.9669 | 7.43 | 0.01 | Selected: the higher-F1 random forest below misses the 15 ms limit |
| Network | improved `max_depth=16` (random forest) | 0.9977 | 0.9982 | 16.15 | 1.18 | Rejected on latency alone (~1 ms over budget on this PC), despite the best F1 of any candidate in the project |

Two results are worth stating plainly rather than smoothing over: the network
domain's best-performing model by a wide margin (F1 0.9982 vs. 0.9669) was
rejected purely because it missed the latency budget by about one millisecond
on the measurement PC, and the SMS domain's selected model scores *lower* on
the held-out test split than the alternative it beat on validation. Both are
direct, intended consequences of ADR-0014's rule that model choice is locked
before the test split is scored, so neither number was adjusted after the
fact.

---

## Section 5: Explainer & Prompt Engineering

The explainer's job is strictly to describe a verdict already made by Tier 1,
never to make or revise it (ADR-0008). This separation exists because SMS and
URL text is attacker-controlled; a language model that treats that text as
instructions could be made to call a real scam safe.

**Planned on-device architecture (design only — see the status note in
Section 2.2):**

- **Model:** Llama 3.2 1B, quantised to 4-bit groupwise weights (the plan
  specifies group sizes such as 32/128/256), with 8-bit dynamic activations in
  the reference `8da4w` export recipe. Norm layers and (depending on the
  recipe) the embedding table stay at higher precision.
- **Export path:** PyTorch model → `torch.export` capture → EXIR (Edge
  dialect) → operators partitioned to the XNNPACK delegate for the Arm CPU →
  serialized `.pte` file → loaded by a C++ ExecuTorch runtime on-device, no
  Python required at inference time.
- **Size estimate:** the BF16 original is approximately 2.46 GB (≈1.24B
  parameters × 2 bytes). The team's own 4-bit target was ≈750 MB, but a
  publicly available 4-bit SpinQuant export was found to be ≈1.0 GiB — larger
  than planned. Both figures are carried forward as *estimates*; see Section
  6 for how the memory budget treats this discrepancy.

**What is actually built today:** the `TemplateRunner`, a deterministic,
rule-based advisory generator keyed off the verdict label (`phishing`,
`spam`, `attack`), each with a fixed one-sentence mechanism explanation and
exactly three numbered defensive steps. It never reads the untrusted text at
all, so it is not merely defended against prompt injection — it is immune to
it by construction. This is the runner the CLI and benchmark actually use;
every advisory shown in this project's demos to date comes from it, not from
Llama.

**Defensive prompt design (the Delimited Prompt Shield, implemented in
`src/explainer/prompt_builder.py`, exercised by tests in
`tests/test_pipeline.py`):**

1. Untrusted text is wrapped between literal markers
   `### BEGIN UNTRUSTED DATA ###` / `### END UNTRUSTED DATA ###`.
2. Marker look-alikes already present in the attacker's text (any case,
   spacing, or `<untrusted...>`-style tag) are regex-replaced with
   `[removed]` before insertion, so the attacker cannot forge a false end
   marker and "escape" the block.
3. Control characters are stripped and the untrusted text is capped at 1,000
   characters.
4. The system prompt explicitly instructs the model that everything inside
   the markers is passive data, never instructions, and that the verdict
   given to it is authoritative and must never be called safe.
5. The model is given only the verdict, the numeric threat score, and a list
   of short, code-computed clues (never raw untrusted text reproduced as
   "facts") as the primary basis for its explanation, per the "feed only
   extracted clues" principle in `docs/executorch_summary.md`.
6. Every output — from either runner — is passed through `validate_advisory`,
   which rejects (in favour of the fixed template) any advisory that: is
   empty; echoes the literal marker text; lacks exactly three numbered steps;
   or, for a genuine threat, contains a "this is safe" / "no threat" claim.

**Honest limitation, stated in the project's own ADR-0016 and repeated here:**
these defences reduce prompt-injection risk; they do not remove it. A
sufficiently crafted attack could still alter the *wording* the model
produces. This is exactly why the block/allow decision is never delegated to
the language model.

---

## Section 6: Edge Optimization

Three optimizations are already measured and in effect for Tier 1; one
(memory for Tier 2) remains a design budget.

- **Single-thread prediction (ADR-0015).** Random-forest models trained with
  all CPU cores showed 41 ms single-sample latency, because thread start-up
  dominates a one-sample inference. Forcing the saved model to one thread
  before persisting it cut this to ≈13 ms. The cost is paid once at training
  time, not per inference.
- **Tree-count reduction (ADR-0017).** The URL forest was reduced from 100 to
  50 trees after the 100-tree version showed a 95th-percentile latency above
  the 15 ms limit (median ≈14 ms, with an unreliable tail). The 50-tree
  forest is smaller and faster; its depth is still chosen on the validation
  split, and its 85-feature input and threshold are unchanged from the
  100-tree version.
- **Single-pass inference, no GPU.** All three Tier 1 detectors are
  scikit-learn estimators (`predict_proba`/linear decision functions) scored
  with one forward pass per event; none require a GPU, matching the zero-GPU
  requirement for a phone target. Peak measured Python memory (tracemalloc,
  model load + 200 predictions) is 5.8 MB (URL), 9.5 MB (SMS), and 1.1 MB
  (network) — all well inside a phone's available headroom.
- **Tier 2 RAM budget — estimate only, not yet measured on any device**
  (from `docs/executorch_summary.md`): target peak resident memory under
  ≈1.1 GB. The KV-cache arithmetic for the 16-layer, 8-head, 64-dim
  architecture gives 32 KB/token, i.e. ≈64 MB at a 2,048-token context. Under
  the optimistic 750 MB model-size plan, estimated peak total is ≈974 MB
  (fits the target); under the more realistic ≈1.0 GiB public export size,
  estimated peak total is ≈1,248 MB (**does not fit** the target). The
  documented fallback order if this is confirmed on-device is: halve the
  context to 1,024 tokens first, then reconsider group size/embedding
  precision, then trim app buffers — with any change recorded as a new ADR.
  Tier 1 detectors are designed to run first and the LLM to load only when an
  alert fires, to keep this peak rare rather than constant.

---

## Section 7: Device Deployment & Benchmarks

**Update (2026-11-21/22, Phase 8):** since this report was first drafted in
Phase 6, the Llama 3.2 1B ExecuTorch export described below as a future plan
was actually attempted and completed. Using `optimum-cli export executorch`
(package `optimum-executorch`) with `--recipe xnnpack --qlinear 8da4w
--qlinear_group_size 128`, a first export quantizing only the linear layers
produced a real, loadable `.pte` file — but at 1,746.5 MB, well over budget,
because Llama 3.2's large vocabulary leaves the embedding/output table
unquantized. Adding `--qembedding 4w --qembedding_group_size 128` to also
quantize the embedding table brought the real, measured file to **827.7 MB**,
within the cautious 1,024 MB budget (see `docs/decisions.md` ADR-0019 and
`docs/executorch_summary.md` Section 3 for full detail). This `.pte` file was
then pushed via `adb push` onto a physical Android device's storage,
confirming the file-transfer pipeline works end-to-end on real hardware.

**What still has not happened, stated plainly:** the `.pte` file has not yet
been loaded and run by an ExecuTorch runtime on the device — that requires
building ExecuTorch's `LlamaDemo` Android app from source (Android Studio,
NDK, and a prebuilt AAR library), which was out of scope for this session.
So actual on-device inference, tokens/sec, peak RAM, and battery draw remain
unmeasured and are marked `TBD` in `docs/on_device_benchmarks.md`. Every
number in Sections 4 and 6 above is still a PC measurement (development
machine, 2026-11-05 run), not a phone inference measurement — the export and
file-transfer milestones above are real and on-device, but they are not the
same as a measured on-device inference run.

**What the benchmark methodology already establishes, ready to be repeated
on-device unchanged (`benchmarks/evaluate_all.py`):**

1. Load the saved model from `models/<domain>_detector.pkl` (trained once;
   this script changes nothing).
2. Score the held-out test split (precision, recall, F1, false-negative rate,
   confusion matrix).
3. Measure median single-prediction latency through the detector's own
   `predict()`, preprocessing included, over 200 single-sample predictions.
4. Measure memory: on-disk file size, and peak Python memory via
   `tracemalloc` across model load plus the same 200 predictions.

Because this is the same measurement code intended for the on-device run, the
Arm/Android numbers that WP7–WP9 will produce should be structurally
comparable to the PC table in Section 4 — but they are a separate
measurement that has not yet been taken, and this report does not estimate
them in place of measuring them.

---

## Section 8: Limitations & Threat Model

**Scope limitation (static, offline features only — ADR-0007).** Every
runtime feature is computed from the item itself: a URL string, SMS text, or
flow record. Nothing is fetched or looked up over a network, by design (this
is what keeps the system private and offline). The direct consequence is that
a brand-new phishing page hosted on an otherwise-clean, previously-trusted
domain cannot be caught by this system — static text/structure features
cannot see it, and no live reputation or content lookup is performed.

**Adversarial evasion and concept drift.**

- *URL:* the detector favours high recall by design (ADR-0011) precisely
  because missing a phishing URL (a false negative) is judged more costly
  than a false alarm. Its actual measured recall is 0.9791 with precision
  0.7510 — i.e., it over-flags legitimate-but-unusual domains at a
  non-trivial rate (995 false positives out of 2,800 legitimate test URLs)
  in exchange for missing only 64 of 3,065 phishing URLs (2.09%).
- *SMS:* the selected model is precision-heavy (0.9855 precision, 0.9067
  recall) — it rarely misclassifies a real message as a scam, but it misses
  7 of 75 scam messages in the test split (9.33%), and a polite scam with no
  urgency or OTP wording is exactly the failure mode the detector is weakest
  against (`docs/threat_explainers.md`).
- *Network:* the deployed model misses 4.28% of attacks (251 of 5,863 in the
  test split); the rejected alternative model would have missed only 0.31%,
  but was excluded purely on the latency limit (Section 4). This is a direct,
  named trade-off between the project's two hard constraints (accuracy vs.
  the 15 ms budget), not an oversight.
- All three datasets are also dated: NSL-KDD reflects 1999 network traffic,
  and the SMS and URL datasets are not current either, so none of the three
  detectors has been exposed to today's newest attack styles.

**Re-use of the held-out test split (ADR-0018).** The Phase 5 benchmark run
re-scored the same test split that was already used once in Phase 3 for model
selection reporting. This is stated here explicitly, as the project's own
ADR requires: Phase 5's numbers are **a reproducibility check on the same
split**, not independent evidence from unseen data. A genuinely fresh test
would require new data collected or downloaded after this point and scored
exactly once with the models unchanged.

**Prompt-injection threat model (Tier 2).** The attacker-controlled surface
is the SMS/URL text passed to the explainer. The Delimited Prompt Shield
(Section 5) is explicitly described in the project's own ADR-0016 as
risk-*reducing*, not risk-*eliminating*: a sufficiently crafted injection may
still change the advisory's wording. The mitigating control is architectural,
not the shield alone — the shield only protects a component (the explainer)
that was already stripped of any authority to change the block/allow
decision.

**Known functional gap.** Raw URL strings submitted to the unified router
currently return `status="unsupported"` rather than a verdict, because the
URL detector requires the 85 precomputed Mendeley columns and no code path
converts a raw address into those columns yet (`src/pipeline/router.py`,
ADR-0012's consequence). The 18-feature lexical extractor exists but is not
wired into the trained model's input.

---

## Section 9: Honest Lessons Learned & Team Contributions

**Concrete problems encountered and how each was resolved, drawn from the
project's own decision log and documents (nothing here is invented beyond
what `docs/decisions.md` and `docs/data_sources.md` already record):**

1. **The NSL-KDD test file could not be trusted.** The official CIC download
   page had gone offline ("this dataset is no longer available"). Two
   unofficial mirrors (Zenodo, GitHub) were located; their *training* files
   matched byte-for-byte, so the Zenodo training file was approved. Their
   *test* files did not match — 306 rows differed in the `service` column —
   so the Zenodo test file was rejected as altered, and the project proceeded
   using only the approved training file, carved into train/val/test splits
   itself. This is slower than trusting a single download, but it caught a
   real data-integrity problem before it reached a trained model.
2. **The URL feature extractor and the URL training data didn't match.** The
   project had already written an 18-feature lexical/entropy extractor
   (ADR-0007-style, from raw URL strings) before discovering that the
   licensed, licence-cleared Mendeley dataset contains no raw URL strings at
   all — only 111 precomputed columns. Rather than discard either piece of
   work, the team split the two roles explicitly (ADR-0012): the Mendeley
   85-column subset became the actual training input, and the 18-feature
   extractor was kept as an explanation/demo utility. This decision is
   recorded so a reader does not assume the two feature sets are the same
   thing.
3. **The best model is not always the deployed model.** In the network
   domain, a random forest outperformed the deployed logistic regression on
   every accuracy metric (F1 0.9982 vs. 0.9669) but was rejected for missing
   the 15 ms latency budget by roughly one millisecond on the measurement
   PC. In the SMS domain, the model selected on validation F1 scored lower
   than its alternative once the test split was opened. Both outcomes were
   accepted as the direct, intended consequence of locking the selection
   rule (validation F1 under the hard limits) before the test split is seen
   (ADR-0014), rather than re-opening the choice after the fact.
4. **A measured number can still be misleading if the methodology isn't
   stated.** The Phase 5 "official benchmark" run initially risked being
   described as a fresh evaluation; the team instead recorded (ADR-0018)
   that it re-scores the same test split already used in Phase 3, and
   constrained every later document (this report included) to say so rather
   than imply new evidence.
5. **A capacity estimate was found to be optimistic before any code was
   written against it.** The team's own 750 MB target for the 4-bit Llama
   export was checked against a real public export and found to be about
   250 MB too optimistic (≈1.0 GiB actual vs. ≈750 MB planned). The team
   recorded both figures and the resulting memory-budget risk (ADR-0009)
   rather than carrying the optimistic number forward silently.

**Team contributions and AI usage.** `docs/ai_usage_log.md` currently records
one entry, for Phase 0 scaffolding. The log has not been kept up to date for
Phases 1–5, even though this report and the ADR history make clear that
substantial AI-assisted work took place in every phase. Before submission,
the team should add one row per phase (or per significant session) naming
which team member ran the session, what the AI tool produced, and what was
checked or changed by hand — the same standard already applied to the Phase 0
entry — both for academic-honesty compliance and because the viva guide
(`TEAM_EXPLAINER_AND_VIVA_GUIDE.md`, intentionally excluded from version
control) is expected to draw on it.

---

### Sources for every figure in this report

All measured numbers above are taken, without alteration, from:
`docs/benchmark_summary.md`, `docs/model_comparison.md`,
`docs/model_cards/{url,sms,network}_detector.md`, `docs/data_splits_summary.md`,
`docs/data_sources.md`, `docs/decisions.md` (ADR-0001 through ADR-0018),
`docs/executorch_summary.md`, `docs/threat_explainers.md`, and
`docs/ai_usage_log.md`. Where a figure is a design estimate rather than a
measurement, it is marked *estimate* in-line, matching the source document's
own labelling.
