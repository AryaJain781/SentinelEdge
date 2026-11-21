# Hardware & Device Checklist (Phase 7 / WP7)

A step-by-step checklist for the human team to work through **before**
starting Android deployment (WP8). Nothing on this list has been executed or
verified by this audit — it is the prerequisite list, not a confirmation
that any team member's phone or workstation already meets it. Check off each
item against real hardware before WP8 begins; do not assume a device
"probably" qualifies.

---

## 1. Phone hardware requirements

| Requirement | Minimum | Recommended | How to check on the phone |
|---|---|---|---|
| RAM | 4 GB | 6 GB or more | Settings → About phone → RAM, or `adb shell cat /proc/meminfo` (see `MemTotal`) |
| CPU architecture | 64-bit Arm (ARM64-v8a) | Same | `adb shell getprop ro.product.cpu.abi` should print `arm64-v8a` |
| Android version | Android 10 (API level 29) | Android 12+ | Settings → About phone → Android version, or `adb shell getprop ro.build.version.sdk` (should be ≥ 29) |
| Free internal storage | 3 GB free | 5 GB+ free (headroom for the ≈1 GB `.pte` file, the APK, logs, and cache) | Settings → Storage, or `adb shell df /data` |

**Why these specific numbers, so the team doesn't treat them as arbitrary:**
the 4 GB RAM minimum follows directly from the ≈1.1–1.2 GB peak-memory
estimate in `docs/mobile_readiness_audit.md` Section 2 plus normal Android
system/app overhead — a device below 4 GB is very unlikely to have enough
free headroom at all. The 64-bit Arm requirement is because ExecuTorch's
XNNPACK delegate targets Arm64; a 32-bit-only device is not a supported
target for this project's plan. Android 10+ is assumed to have the NDK/
runtime support ExecuTorch's Android builds expect — **confirm this against
the ExecuTorch documentation at the time WP8 starts**, since minimum-OS
requirements can change between ExecuTorch releases and this figure was not
independently re-verified for this checklist.

---

## 2. Development workstation setup

- [ ] **Android Studio** installed (a recent stable release; check for
  updates rather than assuming an old install is current).
- [ ] **Android SDK Platform-Tools** installed (this is what provides `adb`).
  Verify with:
  ```
  adb --version
  ```
- [ ] **USB debugging enabled** on the test phone: Settings → About phone →
  tap "Build number" 7 times to unlock Developer Options → Settings →
  Developer options → enable "USB debugging".
- [ ] **OEM unlocking**, only if the deployment plan requires flashing a
  custom build or replacing system partitions (not expected to be necessary
  for installing a normal debug/release APK via `adb install`). If unsure,
  leave OEM unlocking off and only enable it if a specific later step
  explicitly requires it — enabling it unnecessarily weakens the device's
  normal security model.
- [ ] **Device appears in `adb devices`** after connecting via USB and
  accepting the "Allow USB debugging?" prompt on the phone screen:
  ```
  adb devices
  ```
  The device should be listed with status `device` (not `unauthorized` or
  `offline`).
- [ ] **NDK / ExecuTorch Android build prerequisites** — to be confirmed
  against the ExecuTorch documentation links already recorded in
  `docs/executorch_summary.md` Section 6 when WP6/WP8 actually starts the
  export and app build. Not re-verified here.

---

## 3. Model transfer procedure (`.pte` and tokenizer to the phone)

**Status note:** these commands describe the intended transfer mechanism.
There is no `.pte` or tokenizer file to transfer yet (Section 2 of
`docs/mobile_readiness_audit.md`) — this procedure cannot be executed until
WP6 produces those artifacts.

1. Confirm the device is connected and authorized:
   ```
   adb devices
   ```
2. Create the app's private storage directory on the device (replace
   `com.sentineledge.app` with the actual application ID once it is decided
   — it is not fixed yet):
   ```
   adb shell mkdir -p /sdcard/Android/data/com.sentineledge.app/files/models
   ```
3. Push the exported model and tokenizer files from the development machine
   to that directory:
   ```
   adb push model.pte /sdcard/Android/data/com.sentineledge.app/files/models/model.pte
   adb push tokenizer.bin /sdcard/Android/data/com.sentineledge.app/files/models/tokenizer.bin
   ```
4. Verify the files arrived with the expected size (compare against the
   source file size on the development machine; a mismatch means a failed
   or partial transfer):
   ```
   adb shell ls -la /sdcard/Android/data/com.sentineledge.app/files/models/
   ```
5. Confirm free space on the device after the transfer did not drop below
   the 3 GB minimum in Section 1:
   ```
   adb shell df /data
   ```

**Open item for WP8:** whether the app reads these files directly from
`/sdcard/Android/data/<app>/files/` (external app-specific storage, visible
via `adb push` as above) or instead expects them inside the app's internal
storage (which normally requires the app itself to copy them in on first
launch, since `adb push` cannot write directly into another app's private
internal storage on a non-rooted device) is an Android architecture decision
that has not been made yet. Record that decision as a new ADR when WP8
starts, and update this procedure to match — do not assume the simpler
external-storage path above is the final answer.

---

## 4. Sign-off

Before WP8 begins, each row below should be checked against a real device
and a real workstation, by a named team member, with the date — not
assumed from this checklist alone:

| Item | Verified on real hardware? | By whom | Date |
|---|---|---|---|
| Phone meets RAM/CPU/OS/storage minimums (Section 1) | ☐ | | |
| Android Studio + platform-tools installed (Section 2) | ☐ | | |
| `adb devices` shows the phone as authorized (Section 2) | ☐ | | |
| ExecuTorch Android build prerequisites confirmed against current docs (Section 2) | ☐ | | |
