# On-Device Benchmark Report (Phase 8 / WP8)

**This document contains no measured numbers.** No physical Android device
run of any part of this pipeline has happened as of this writing — the
Llama/ExecuTorch export does not exist (`docs/mobile_readiness_audit.md`
Section 2), and no Tier 1 model has been pushed to a phone yet. Every value
below is marked `TBD`. Filling in a plausible-looking number without an
actual device measurement would violate this project's own evaluation
protocol (ADR-0014, ADR-0018) and must not be done, including under
deadline pressure — an evaluator can and should ask how each number was
produced.

Fill in this table only from real measurements, with the method actually
used recorded next to each number (not just the number), on the real test
phone from `docs/hardware_checklist.md`.

---

## 1. What to measure, and exactly how

| Metric | What it means here | How to measure it |
|---|---|---|
| **Peak RAM usage (MB)** | The highest resident memory the app (or, if testing the demo app separately per `deploy/android_guide.md`, that app) reaches while a Tier 2 explanation is being generated — this is where `docs/mobile_readiness_audit.md`'s ≈1.1–1.2 GB budget risk lives. | `adb shell dumpsys meminfo <package_name>` sampled repeatedly during generation (e.g., once per second via a loop), taking the max of the `TOTAL PSS` value. Android Studio's Profiler (Memory tab) gives the same information graphically and is easier to screenshot for the report. |
| **Tokens per second (decode throughput)** | How fast the on-device Llama model generates output tokens once it starts — this is the number that determines whether a 3-step advisory feels instant or sluggish to the user. | Instrument the ExecuTorch runtime call (or the demo app, if testing that first) to log a timestamp per generated token, then compute `(token_count - 1) / (t_last - t_first)` over the generation. Do not compute this from wall-clock-of-whole-response divided by token count alone without excluding time-to-first-token (see next row) — that would understate throughput. |
| **Time to first token (TTFT, ms)** | The delay between the detector verdict being ready and the first explanation token appearing — this is the latency the user actually perceives as "is it thinking." | Timestamp at prompt submission to the runtime, timestamp at first token callback; report the difference. Measure separately from total generation time, not derived from it. |
| **Battery temperature delta (°C)** | How much the device heats up under sustained use — relevant because thermal throttling can silently slow down later inferences in a benchmark run, confounding the other three numbers if not tracked. | `adb shell dumpsys battery | findstr temperature` (Linux/macOS: `grep temperature`) immediately before the first test vector and immediately after the last, same session, device not charging during the test. Report the delta, and note ambient conditions (charging state, screen on/off, case on/off) since these all affect it. |

---

## 2. Measurement protocol (so the numbers are comparable across runs)

1. Let the device sit idle, screen off, not charging, for at least 5
   minutes before starting, so the "before" temperature reading isn't
   already elevated from unrelated prior use.
2. Run the three test vectors from `docs/airplane_mode_verification.md`
   Section 4, in airplane mode, in the same session as that protocol if
   convenient — the two reports can share one device run.
3. Record all four metrics per vector, not just once for the whole session,
   so a reader can see whether e.g. the third vector is slower than the
   first (which would suggest thermal throttling or memory pressure
   building up, not a fixed per-call cost).
4. Repeat the full three-vector run at least 3 times and report median
   values, the same way `benchmarks/evaluate_all.py` reports a median over
   200 PC-side runs rather than a single sample — a single on-device run is
   not enough to distinguish a real number from noise.

---

## 3. Results table (fill in after real measurement only)

| Run | Vector | Peak RAM (MB) | Tokens/sec | TTFT (ms) | Battery Δ°C (session total) |
|---|---|---|---|---|---|
| 1 | SMS | TBD | TBD | TBD | TBD |
| 1 | URL | TBD | TBD | TBD | TBD |
| 1 | Network | TBD | TBD | TBD | TBD |
| 2 | SMS | TBD | TBD | TBD | — |
| 2 | URL | TBD | TBD | TBD | — |
| 2 | Network | TBD | TBD | TBD | — |
| 3 | SMS | TBD | TBD | TBD | — |
| 3 | URL | TBD | TBD | TBD | — |
| 3 | Network | TBD | TBD | TBD | — |
| **Median** | | **TBD** | **TBD** | **TBD** | **TBD** |

**Device used:** TBD (make/model, RAM, Android version, confirmed against
`docs/hardware_checklist.md` Section 1)
**ExecuTorch/export version used:** TBD (must match between export and
runtime, per `deploy/android_guide.md` Section 2)
**Date measured:** TBD

---

## 4. Comparison against budgets already set elsewhere in this project

Once Section 3 is filled in, compare against:

- Peak RAM vs. the ≈1.1–1.2 GB target in `docs/mobile_readiness_audit.md`
  Section 2.
- TTFT and tokens/sec have **no prior budget set anywhere in this
  project's documents** — this is new information this benchmark produces,
  not a pass/fail check against an existing number. Do not retroactively
  invent a target and claim it was "met."
- Detector latency (the `<25 ms` criterion) belongs in
  `docs/airplane_mode_verification.md`, not here — do not duplicate or
  re-derive it in this document to avoid the two reports drifting out of
  sync.
