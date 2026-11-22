# Zero-Cloud / Airplane Mode Verification Protocol (Phase 8 / WP8)

**Status: a protocol to execute on real hardware, not a record of a result.**
This document defines exactly what "pass" means and how to check it. It
contains no measured numbers, because no physical device run has happened
yet. Fill in the results table in Section 5 when the team actually runs
this, and do not report it as done until that table has real numbers in it.

**One real gap to resolve before this protocol can run as literally
written:** the second test vector below is specified as "a phishing banking
URL." As of this project's current code
(`src/pipeline/router.py`, ADR-0012), **a raw URL string is not analysable
yet** — `analyze()` returns `status="unsupported"` for any raw web address,
because the URL detector needs the 85 precomputed Mendeley columns
(`docs/data_sources.md`), and no code path converts a raw address into those
columns. Before running this protocol, the team must either (a) feed the
85-column precomputed feature vector directly, bypassing the "type in a URL"
framing, or (b) implement a raw-URL-to-85-features extractor first and
record that as a new ADR. Do not quietly substitute a precomputed-feature
input while still describing the demo as "typed a URL" in front of an
evaluator — say plainly which of (a) or (b) was done.

---

## 1. Preconditions

- [ ] `v1.0-pre-hardware` tag checked out (or later), per
  `docs/decisions.md` and the Phase 7 freeze.
- [ ] `docs/hardware_checklist.md` Section 1 confirmed on the actual test
  phone (not assumed).
- [ ] The Tier 1 detectors and Tier 2 explainer are actually installed and
  runnable on the device per `deploy/android_guide.md` — this protocol
  tests behavior, not installation; do the install first.
- [ ] A second device or a packet-capture point (e.g., a test Wi-Fi access
  point the team controls, with its own traffic log) is available as an
  **independent** witness that no traffic left the phone — see Section 3.
  Relying solely on the phone's own airplane-mode indicator is weaker
  evidence than an independent network-side witness.

---

## 2. Network isolation steps

1. On the test phone, open Settings → Network & internet → **Airplane
   mode** → enable it.
2. Confirm **all three** radios are off individually, not just the airplane
   toggle (some OEM skins leave Wi-Fi or Bluetooth re-enabled even in
   airplane mode unless toggled separately):
   - Wi-Fi: off
   - Mobile/cellular data: off (airplane mode should force this, but check)
   - Bluetooth: off
3. Confirm via `adb` (still connected over USB, which is not a network
   radio and does not violate the test):
   ```
   adb shell settings get global airplane_mode_on
   ```
   Expect `1`.
4. Independently confirm no Wi-Fi association exists:
   ```
   adb shell dumpsys wifi | findstr /i "Wi-Fi is" 
   ```
   (On macOS/Linux use `grep -i` instead of `findstr /i`.) Expect output
   indicating Wi-Fi is disabled, not merely "disconnected."

---

## 3. Independent network witness (do this, don't skip it)

Airplane mode disables the radios at the OS level, which is strong
evidence by itself — but the stronger, independent proof for a viva is
showing that **no packet reached any network the team controls**, not just
trusting the phone's own toggle:

- If a test Wi-Fi access point is available: run `tcpdump` (or the
  access point's own client-traffic log) on it throughout the test and
  confirm the test phone's MAC address never appears, before, during, or
  after the three test vectors in Section 4.
- If no controlled access point is available: at minimum, run
  `adb shell dumpsys netstats` before and after the test and confirm the
  per-UID byte counters for the SentinelEdge app process are unchanged
  (0 bytes sent, 0 bytes received) across the test window. This is weaker
  than an external witness (it trusts the phone's own accounting) and
  should be reported as such.

---

## 4. Test vectors

Three vectors, run in airplane mode, with the app's own timestamped log (or
screen recording) as the record of what happened and when:

| # | Vector | Example input | What it should trigger |
|---|---|---|---|
| 1 | Malicious KYC SMS | `"URGENT: Your KYC verification has expired. Share your Aadhaar-linked OTP within 24 hours to avoid account suspension: http://bit.ly/x1"` | SMS detector flags `spam`; explainer produces a mechanism sentence + 3 numbered steps |
| 2 | Phishing banking URL | A precomputed 85-feature vector matching a known-phishing row from the Mendeley test split (see the status note above — not a raw typed URL, unless the raw-URL extractor has been built first) | URL detector flags `phishing`; explainer produces a mechanism sentence + 3 numbered steps |
| 3 | Anomaly network packet/flow | A precomputed 41-field NSL-KDD-style flow record matching a known-attack row from the network test split | Network detector flags `attack`; explainer produces a mechanism sentence + 3 numbered steps |

For each vector, record:

1. **Classical detector verdict and timestamp.** Pass criterion: verdict
   produced in **under 25 ms**, measured on-device (not the PC's 15 ms
   figure from `docs/benchmark_summary.md` — the Phase 8 brief sets a
   separate, looser on-device budget; do not conflate the two numbers).
2. **Explainer output.** Pass criterion: a plain-English mechanism
   explanation plus exactly 3 numbered defensive steps, produced entirely
   on-device, matching the format `validate_advisory()` already checks
   (`src/explainer/prompt_builder.py`).
3. **Network witness result from Section 3** for the whole vector's
   duration, both the detector step and the explainer step. Pass criterion:
   zero packets/zero bytes from the device.

---

## 5. Results (fill in only after a real device run — no placeholders left as fabricated numbers)

| Vector | Detector verdict | Detector latency (ms) | Explainer produced on-device? | 3 steps present? | Network bytes observed | Pass/Fail |
|---|---|---|---|---|---|---|
| 1. SMS | *(to be measured)* | *(to be measured)* | | | | |
| 2. URL | *(to be measured)* | *(to be measured)* | | | | |
| 3. Network | *(to be measured)* | *(to be measured)* | | | | |

**Overall pass criterion:** all three rows pass, independently. A single
failing row means the protocol fails overall — do not average or round up.

**Tester:** _____________ **Device:** _____________ **Date:** _____________
