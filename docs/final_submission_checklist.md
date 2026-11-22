# Final Submission Checklist

| Item | Status | Notes |
|---|---|---|
| GitHub repository URL | ✅ Ready | `https://github.com/AryaJain781/SentinelEdge` — public, up to date through Phase 7 (`9109de8`); Phase 8/9 docs pending upload (see below) |
| Technical report (PDF) | ⬜ Needs export | `docs/technical_report.md` exists and is current; export to PDF (e.g. via a Markdown-to-PDF tool, or open in a Markdown viewer and "Print to PDF") before submission — the PRD requires a PDF, and the repo currently only has the Markdown source |
| Demonstration video link | ⬜ Needs recording + upload | `docs/demo_video_script.md` is written and ready to record against; once recorded, upload (YouTube unlisted / Drive link / submission portal, per your institution's instructions) and paste the link into this checklist and into the README |
| Team contribution log | ⬜ Needs content | Not yet created in this repo — if this is a solo submission, a short note ("All work — detectors, pipeline, explainer, documentation, deployment design — completed by Abhilasha Kumari, MT26CSE012") in `docs/ai_usage_log.md` or a new `docs/contributions.md` satisfies this; if there were teammates, list each person's phases/modules |
| PRD Section 3 compliance audit | ✅ Done | `docs/prd_compliance_audit.md` — zero cloud keys/tokens, clean `.gitignore`, last full test run 156 passed / 2 skipped / 0 failed |
| `check.ps1` clean on final code | ⬜ Re-run recommended | Last clean run predates the Phase 8 `deploy/` scripts; re-run once those are added so lint/format covers them too |
| Phase 8 deliverables pushed to GitHub | ⬜ Pending upload | `export_detectors.py`, `validate_mobile_parity.py`, `export_llama_pte.py`, `android_guide.md`, `airplane_mode_verification.md`, `on_device_benchmarks.md` — written, not yet on `origin/main` |
| Phase 9 deliverables pushed to GitHub | ⬜ Pending upload | This checklist, `prd_compliance_audit.md`, `demo_video_script.md` — written, not yet on `origin/main` |
| Viva cheat-sheet section | ⬜ Needs manual paste | Text prepared separately (not committable — `TEAM_EXPLAINER_AND_VIVA_GUIDE.md` is gitignored by design); paste into your local copy before the viva |
| README reflects final state | ✅ Mostly done | WP5/WP6 rows updated in Phase 6; consider adding a one-line pointer to the video link and PDF report once those exist |

## What "done" looks like for submission
1. Upload the 6 Phase 8 files + 3 Phase 9 files to GitHub (same manual web-upload workflow used for Phases 6–7).
2. Export `docs/technical_report.md` to PDF.
3. Record the video per `docs/demo_video_script.md`, upload it, and drop the link in this table and the README.
4. Add a one-line contribution/authorship note.
5. Re-run `check.ps1` once Phase 8 files are included, to keep the "100% clean" claim accurate for the whole repo.
6. Paste the viva cheat-sheet text into your local `TEAM_EXPLAINER_AND_VIVA_GUIDE.md`.

Nothing above is blocked on hardware or on the Hugging Face token — all of it can be finished today except the parts that explicitly need you to record/export/upload (recording a video, exporting a PDF) rather than something I can do from here.
