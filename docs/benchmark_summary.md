# Benchmark Summary (official run)

Run date: 2026-11-05. Seed 42. Models: saved Phase 3 detectors, unchanged.

Latency and memory are measured on this PC. Phone numbers come in Phase 4 measurements.

| Domain | Model | Test rows | Precision | Recall | F1 | Missed threats | Latency median (ms) | Size (MB) | Peak memory (MB) | Limits met | Matches Phase 3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| url | improved (max_depth=16) | 5,865 | 0.7510 | 0.9791 | 0.8500 | 0.0209 | 9.03 | 1.18 | 5.8 | yes | yes |
| sms | baseline (alpha=0.1) | 558 | 0.9855 | 0.9067 | 0.9444 | 0.0933 | 3.94 | 0.51 | 9.5 | yes | yes |
| network | baseline (C=1.0) | 12,598 | 0.9768 | 0.9572 | 0.9669 | 0.0428 | 7.62 | 0.01 | 1.1 | yes | yes |

Limits: latency under 15 ms, model file under 25 MB.

Confusion matrices (TN / FP / FN / TP):

- url: 1805 / 995 / 64 / 3001
- sms: 482 / 1 / 7 / 68
- network: 6602 / 133 / 251 / 5612
