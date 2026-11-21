# Mobile Readiness Audit (Phase 7 / WP7)

**Purpose:** before any hardware work starts, record exactly what each trained
artifact is, what runtime it would need on an Android phone, and what could
go wrong in that conversion — so the team freezes the PC pipeline (Section 3)
with eyes open about what Phase 8 (Android deployment) still has to solve.

**What this document is not:** it is not a record of conversions already
done. No `.onnx`, `.pte`, or Treelite artifact exists yet in this repository
or in `models/`. Every runtime choice below is a recommendation for WP8 to
implement and measure, not a completed step.

---

## 1. Tier 1 micro-detectors: model, features, and target mobile runtime

| Detector | Model class (as trained) | Input to the model | Feature dimension | File | Measured PC size / latency |
|---|---|---|---|---|---|
| URL phishing | `RandomForestClassifier` (`n_estimators=50, max_depth=16`), scikit-learn | 85 numeric URL-string features (ADR-0012), no categorical encoding needed | 85 | `models/url_detector.pkl` | 1.12–1.18 MB / 9.0–9.1 ms |
| SMS scam | `MultinomialNB` (`alpha=0.1`) on top of a `ColumnTransformer` with `TfidfVectorizer(ngram_range=(1,2), min_df=2, sublinear_tf=True)` | Raw SMS text (cleaned) + 8 numeric metadata columns | TF-IDF vocabulary size is **not fixed** — it is whatever the training corpus produced (no `max_features` cap was set), plus 8 metadata columns | `models/sms_detector.pkl` | 0.51 MB / 3.94 ms |
| Network attack | `LogisticRegression` (`C=1.0`) on top of a `ColumnTransformer` with `OneHotEncoder(handle_unknown="ignore")` on 3 categorical fields | 38 numeric NSL-KDD fields + 3 one-hot-encoded categorical fields (`protocol_type`, `service`, `flag`) | 38 numeric + one-hot width for 3 categorical columns. **Not independently measured in this audit** — the exact post-encoding width depends on how many distinct `service`/`flag`/`protocol_type` values existed in the training split. Before WP8 starts, run `onehot.get_feature_names_out()` on the saved pipeline and record the exact number here; do not guess it from the public NSL-KDD documentation, since `handle_unknown="ignore"` already shows the team is aware the training-time cardinality is what matters, not a textbook figure. | `models/network_detector.pkl` | 0.01 MB / 7.4–7.6 ms |

### Candidate target runtimes for Tier 1, and why

Three realistic options exist for getting an already-fitted scikit-learn
`Pipeline` onto an Android phone. None has been chosen or implemented yet;
this is the comparison WP8 should start from.

| Runtime | How it would work | Fit for this project | Main risk |
|---|---|---|---|
| **ONNX Runtime Mobile** | Export each `Pipeline` with `skl2onnx`/`onnxmltools`, bundle the `.onnx` graph, run it with the ORT Mobile Android AAR. | Good fit for the logistic-regression (network) and random-forest (URL) pipelines, which `skl2onnx` supports well. **Likely to struggle with `TfidfVectorizer`** — scikit-learn's text vectorizer is only partially supported by `sklearn-onnx`'s `CountVectorizer`/`TfidfVectorizer` converters, and an unbounded, data-dependent vocabulary (see table above) makes the exported graph's size unpredictable until it is actually tried. | TF-IDF export fidelity for the SMS detector; needs to be prototyped before being assumed to work. |
| **Treelite + C++ runtime** | Compile the random-forest (URL) model to native C/C++ with Treelite, link it into the Android app via JNI. | Excellent fit for the URL random forest specifically (Treelite targets exactly this model family and produces very small, very fast native code). | Does not help the logistic-regression or Naive-Bayes/TF-IDF models at all — Treelite is tree-model-only, so it would only solve one of the three detectors, not all three uniformly. |
| **Chaquopy (embedded CPython + scikit-learn on-device)** | Ship the actual `.pkl` files and run the real scikit-learn `predict()` inside a Python interpreter embedded in the Android app via Chaquopy. | Simplest to get correct — it is bit-for-bit the same code already tested on the PC, including the exact `TfidfVectorizer` vocabulary, so there is no re-implementation or conversion-fidelity risk at all. | Heaviest at runtime: ships a Python interpreter plus scikit-learn/numpy/pandas inside the APK, with real but unquantified APK-size and cold-start cost. Must be benchmarked against the 15 ms latency budget on-device, not assumed to meet it just because the PC numbers do. |

**Recommendation for WP8 to evaluate, not a decision made here:** start with
Chaquopy for correctness (zero conversion-fidelity risk across all three
models), measure its actual latency and APK-size cost on a real device, and
only move the URL random forest to Treelite if Chaquopy's latency misses the
15 ms budget on-device. Do not attempt the ONNX path for the SMS detector
without first prototyping the `TfidfVectorizer` export in isolation.

### Conversion risks common to all three detectors

- **Floating-point precision loss.** Any conversion path that re-implements
  inference outside scikit-learn's own code (ONNX, Treelite) can produce
  slightly different probabilities than the PC numbers in
  `docs/benchmark_summary.md`, because of different floating-point
  reduction order or reduced-precision kernels. If a non-Chaquopy runtime is
  used, the team must re-run the exact same precision/recall/F1 evaluation
  from `benchmarks/evaluate_all.py` against the converted model's output on
  the same held-out test rows, and record any divergence — a silent
  assumption that "it's the same model" is not acceptable after a format
  conversion.
- **Unsupported operators.** `OneHotEncoder(handle_unknown="ignore")` and a
  `ColumnTransformer` mixing text and numeric columns are both more complex
  graphs than a single estimator; confirm each operator in the exported graph
  is actually supported by the chosen mobile runtime's operator set before
  assuming export success from a library version number alone.
- **Memory allocation on 4 GB/6 GB devices.** Tier 1 models themselves are
  tiny (≤1.2 MB on disk, ≤9.5 MB peak Python memory measured on the PC per
  `docs/benchmark_summary.md`) and are not expected to be the memory
  pressure point — Section 2 below is where the real budget risk is.

---

## 2. Tier 2: Llama 3.2 1B artifact plan

**Status: not built.** `src/explainer/runtime.py`'s `ExecuTorchRunner` is a
stub that unconditionally raises `RunnerUnavailable` — no `.pte` file has
been exported, and nothing here has been measured on a device. This section
records the target artifact and budget from `docs/executorch_summary.md` and
ADR-0009, so the freeze in Section 3 is honest about what it is and is not
freezing.

| Artifact | Target | Status |
|---|---|---|
| `model.pte` | 4-bit groupwise-quantised Llama 3.2 1B, exported via `torch.export` → EXIR → XNNPACK delegate → serialized `.pte` | Not exported. Planned size: team's own target ≈750 MB (optimistic); a public SpinQuant 4-bit export is ≈1.0 GiB (more realistic) — ADR-0009 |
| `tokenizer.bin` (or equivalent tokenizer file for the chosen export recipe) | Llama 3.2's tokenizer, packaged alongside the `.pte` file so the on-device runtime can encode/decode without network access | Not produced. No tokenizer file exists in this repository; the exact filename and format depend on which export tool (`optimum-cli export executorch`, or a prequantized community `.pte`) is ultimately used, and must be pinned down and recorded here when WP6/WP8 starts, not assumed to be named `tokenizer.bin` from a template |
| Quantization parameters | 4-bit groupwise weights (group size such as 32/128/256, smaller = more accurate but more scale-value overhead), 8-bit dynamic activations in the reference `8da4w` recipe, norm layers kept at higher precision | Design choice only (`docs/executorch_summary.md` Section 3); no group size has been fixed or measured yet |
| Peak resident memory budget | **Target: under ≈1.1–1.2 GB total** | Estimate only. Under the optimistic 750 MB model size, estimated total ≈974 MB (fits). Under the more realistic ≈1.0 GiB public export size, estimated total ≈1,248 MB (**does not fit** a 1.1 GB target, and is right at the edge of even a 1.2 GB target) |

### Memory budget breakdown (from `docs/executorch_summary.md`, carried forward unchanged — these are estimates, not measurements)

| Component | Plan (750 MB model) | Cautious (1.0 GiB model) |
|---|---|---|
| Model weights (4-bit) | 750 MB | 1,024 MB |
| KV cache (2,048-token context; 32 KB/token for this architecture) | 64 MB | 64 MB |
| Activations and scratch buffers | 100 MB | 100 MB |
| ExecuTorch runtime and XNNPACK | 50 MB | 50 MB |
| Tier 1 detectors (compact tables) | 10 MB | 10 MB |
| App code, UI and buffers | 100 MB | 100 MB |
| **Total (estimate)** | **≈974 MB** | **≈1,248 MB** |

### Conversion risks specific to the Llama export

- **Unsupported ExecuTorch/XNNPACK operators.** Not every PyTorch operator in
  a Llama-family model is guaranteed to have an XNNPACK delegate kernel;
  anything that falls back to default ExecuTorch kernels will be slower than
  planned, and this has not been checked against the actual exported graph
  because no export has been attempted yet.
- **Precision loss from 4-bit groupwise quantization.** This is an accuracy
  risk, not just a size one — the explainer's output quality has never been
  evaluated at 4-bit precision (there is no baseline to compare against,
  since the model has never been run at all). WP6 must budget time for a
  qualitative check of advisory quality after quantization, not only a
  memory/latency measurement.
- **Memory allocation on 4 GB RAM devices.** The cautious-case total
  (≈1,248 MB) already exceeds the project's own ≈1.1 GB target before
  accounting for whatever else Android itself and other running apps hold —
  on a 4 GB device this is a real risk of the OS killing the app under memory
  pressure, not merely "it fits awkwardly." The documented fallback order
  (reduce context to 1,024 tokens, then revisit group size/embedding
  precision, then trim app buffers) has not been exercised or measured on
  real hardware. **A 4 GB device should be treated as the risk case to test
  first**, not the 6 GB+ device, precisely because this is where the budget
  is tightest.
- **No fallback if the budget still doesn't fit.** If trimming all three
  levers above still does not bring peak memory under budget on a real 4 GB
  device, the team does not currently have a documented next option (for
  example, dropping to a smaller model, or making the LLM explainer an
  optional/downloadable component rather than bundled). This should be
  decided and recorded as a new ADR before WP8 commits to a device matrix.

---

## 3. What "frozen" means for this milestone

The `v1.0-pre-hardware` tag (Section 3 of the Phase 7 brief; git commands
below) freezes:

- The three trained Tier 1 detector `.pkl` files and their training/
  evaluation code (Phases 2–3).
- The unified router and Delimited Prompt Shield (Phase 4/WP5).
- The `TemplateRunner` explainer, which is what actually produces advisories
  today.
- All documentation through Phase 6, including this audit.

It explicitly does **not** freeze, because none of it exists yet to freeze:
the Llama `.pte` export, the tokenizer artifact, any ONNX/Treelite/Chaquopy
conversion of the Tier 1 models, or any Android project code. Those remain
open work for WP6 (the ExecuTorch-export sense of that label) and WP8.
