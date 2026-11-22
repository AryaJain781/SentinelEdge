# Android Integration & Execution Guide (Phase 8 / WP8)

**Status of this guide: a procedure to follow, not a record of something
already done.** No Android project exists in this repository yet (`deploy/`
held only this and the other Phase 8 documents before this guide was
written). Nobody on the team has run these steps end-to-end. Treat every
step as "try this, then correct this document if it's wrong" rather than
"this is known to work."

This assumes `docs/hardware_checklist.md` (Phase 7) is already satisfied:
a real Arm64 Android 10+ phone with 4 GB+ RAM, Android Studio, and `adb`
working (`adb devices` shows the phone as `device`, not `unauthorized`).

---

## 1. Two integration options, and which to start with

| Option | What it is | When to use it |
|---|---|---|
| **ExecuTorch Android demo app** | Meta's own sample Android app that loads a `.pte` file and a tokenizer and runs text generation, with a basic chat UI already built. Source: the `executorch` GitHub repo's `examples/demo-apps/android` directory (see `docs/executorch_summary.md` Section 6 for the repository link). | Start here. It proves the `.pte` export actually loads and runs on a real phone before writing any custom integration code. Do this first, separately from SentinelEdge's own detectors. |
| **Custom native C++/JNI harness inside the SentinelEdge app** | A purpose-built Android app that embeds the ExecuTorch C++ runtime via JNI, feeds it prompts built by `src/explainer/prompt_builder.py`, and surfaces the detector verdicts from Section 2 below. | Only after the demo app confirms the `.pte` file itself works. This is genuinely new engineering work (the Android project does not exist yet) and should not be the first thing attempted. |

---

## 2. Step-by-step: running the ExecuTorch demo app first

1. Clone the ExecuTorch repository on the development workstation (not the
   phone) and check out the release tag matching the `executorch` Python
   package version used for the export in `deploy/export_llama_pte.py`.
   Using mismatched export-time and runtime-time ExecuTorch versions is a
   common source of "the file loads but produces garbage" bugs — pin both
   to the same release.
2. Follow the demo app's own `README` under
   `examples/demo-apps/android/LlamaDemo/` to open it in Android Studio.
   This project does not duplicate that README's exact Gradle/NDK setup
   steps here, because it is Meta's own build and changes with ExecuTorch
   releases — follow the version actually checked out in step 1, not a
   copy pasted into this file that could go stale.
3. Build the app for `arm64-v8a` specifically (the checklist in
   `docs/hardware_checklist.md` requires this architecture). Confirm the
   Gradle `abiFilters` or equivalent setting targets `arm64-v8a`, not a
   universal/multi-ABI build that would also pull in unnecessary binaries.
4. Push the exported artifacts from `deploy/export_llama_pte.py`'s output
   directory to the phone (commands below), then install and run the demo
   app, pointing it at those files through whatever file-picker or config
   the demo app provides.
5. **Before measuring anything**, confirm basic generation works at all: a
   short prompt produces a plausible, non-garbled response. If it does not,
   stop and debug the export (Section 1's ExecuTorch-version mismatch is
   the first thing to check) before moving to SentinelEdge-specific
   integration.

---

## 3. Pushing weights to the phone (`adb push`)

Two destinations are shown because they serve different purposes — use the
first for the demo app, and decide on the second only once the custom app's
package name exists.

**a) `/data/local/tmp/` — world-readable shell storage, fastest to iterate
with, good for the demo-app step above:**

```bash
adb push models/llama/llama3_2_1b_4bit.pte /data/local/tmp/
adb push models/llama/tokenizer.bin /data/local/tmp/
```

Verify the push:

```bash
adb shell ls -la /data/local/tmp/
```

**b) The app's own sandboxed storage — for the eventual SentinelEdge app,
once its application ID is decided (not yet, per `docs/mobile_readiness_audit.md`):**

```bash
adb shell mkdir -p /sdcard/Android/data/<application-id>/files/models
adb push models/llama/llama3_2_1b_4bit.pte /sdcard/Android/data/<application-id>/files/models/
adb push models/llama/tokenizer.bin /sdcard/Android/data/<application-id>/files/models/
```

`/data/local/tmp/` is fine for the demo app and for manual testing, but it
is world-readable shell storage — **do not rely on it for a real release
build**; the final app should copy or read the model from its own
sandboxed storage, consistent with the "no data leaves the device" promise
in `README.md`.

**Also push the Tier 1 detector artifacts from `deploy/export_detectors.py`**,
the same way, to whichever location the chosen Tier 1 runtime
(ONNX Runtime Mobile, Treelite, or Chaquopy — see
`docs/mobile_readiness_audit.md` Section 1) expects them. That decision has
not been made yet; update this section once it is.

---

## 4. Wiring SentinelEdge's own pipeline into the app (custom harness)

This is the part that does not exist yet and needs real engineering, listed
here so WP8 has a concrete starting checklist rather than an open-ended
task:

1. Decide the Tier 1 runtime per `docs/mobile_readiness_audit.md` Section 1
   (Chaquopy recommended there as the starting point for correctness) and
   record that decision as a new ADR.
2. Port (or reuse via Chaquopy, if chosen) `src/pipeline/router.py`'s
   `analyze()` logic so an Android event (an intercepted SMS, a tapped
   link, a captured flow summary — the actual Android-side interception
   mechanism for each is itself undesigned and out of this guide's scope)
   reaches a detector and produces a `Verdict`.
3. On a flagged verdict, build the prompt via the same `build_prompt()` /
   `sanitize_untrusted()` logic as `src/explainer/prompt_builder.py` — do
   not reimplement the Delimited Prompt Shield differently on-device; the
   whole point of ADR-0016 is that this logic is tested once and reused.
4. Feed that prompt to the ExecuTorch runtime loaded via JNI, exactly as
   the demo app does in Section 2, but driven by SentinelEdge's own code
   path instead of the demo's chat UI.
5. Run the output through the same `validate_advisory()` check before
   display — this must not be skipped on-device just because it is
   "just a demo."

---

## 5. What this guide does not cover yet

- The actual Android `AndroidManifest.xml`, package structure, and UI for
  SentinelEdge's own app — none of that exists in this repository.
- How an SMS/URL/network event is actually intercepted on Android (requires
  OS-level permissions and APIs not yet selected).
- Signing/release-build configuration.

These are open WP8 items, not omissions from this guide.
