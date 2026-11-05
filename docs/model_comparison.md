# Model Comparison (Phase 3)

Trained 2026-11-05 with seed 42. Hyperparameters and thresholds were chosen on the **validation** split. The **test** split was scored once, for reporting only.

Latency is measured on this PC (median of 200 single-sample predictions, including preprocessing). Phone timings must be measured on the device.

Limits: size < 25 MB, latency < 15 ms.

## NETWORK

### Test split (final, reported once)

| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | Size (MB) | Latency (ms, median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline: C=1.0 **(selected)** | 0.9768 | 0.9572 | 0.9669 | 0.0428 | 6602 / 133 / 251 / 5612 | 0.01 | 7.804 |
| improved: max_depth=16 | 0.9995 | 0.9969 | 0.9982 | 0.0031 | 6732 / 3 / 18 / 5845 | 1.18 | 15.981 |

### Validation split (used for selection)

| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | Size (MB) | Latency (ms, median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline: C=1.0 | 0.9759 | 0.9688 | 0.9724 | 0.0312 | 6594 / 140 / 183 / 5680 | 0.01 | 7.804 |
| improved: max_depth=16 | 0.9991 | 0.9962 | 0.9977 | 0.0038 | 6729 / 5 / 22 / 5841 | 1.18 | 15.981 |

### All hyperparameter values tried (validation)

| Family | Setting | Threshold | Validation F1 | Recall |
|---|---|---:|---:|---:|
| baseline | C=0.1 | 0.50 | 0.9693 | 0.9633 |
| baseline | C=1.0 | 0.50 | 0.9724 | 0.9688 |
| improved | max_depth=12 | 0.50 | 0.9968 | 0.9944 |
| improved | max_depth=16 | 0.50 | 0.9977 | 0.9962 |

## SMS

### Test split (final, reported once)

| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | Size (MB) | Latency (ms, median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline: alpha=0.1 **(selected)** | 0.9855 | 0.9067 | 0.9444 | 0.0933 | 482 / 1 / 7 / 68 | 0.51 | 3.970 |
| improved: C=10.0 | 0.9859 | 0.9333 | 0.9589 | 0.0667 | 482 / 1 / 5 / 70 | 0.40 | 6.969 |

### Validation split (used for selection)

| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | Size (MB) | Latency (ms, median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline: alpha=0.1 | 1.0000 | 0.9189 | 0.9577 | 0.0811 | 483 / 0 / 6 / 68 | 0.51 | 3.970 |
| improved: C=10.0 | 0.9571 | 0.9054 | 0.9306 | 0.0946 | 480 / 3 / 7 / 67 | 0.40 | 6.969 |

### All hyperparameter values tried (validation)

| Family | Setting | Threshold | Validation F1 | Recall |
|---|---|---:|---:|---:|
| baseline | alpha=0.1 | 0.50 | 0.9577 | 0.9189 |
| baseline | alpha=0.5 | 0.50 | 0.9037 | 0.8243 |
| baseline | alpha=1.0 | 0.50 | 0.8788 | 0.7838 |
| improved | C=1.0 | 0.50 | 0.8921 | 0.8378 |
| improved | C=10.0 | 0.50 | 0.9306 | 0.9054 |

## URL

### Test split (final, reported once)

| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | Size (MB) | Latency (ms, median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline: C=1.0 | 0.7324 | 0.9768 | 0.8371 | 0.0232 | 1706 / 1094 / 71 / 2994 | 0.00 | 4.948 |
| improved: max_depth=16 **(selected)** | 0.7538 | 0.9781 | 0.8515 | 0.0219 | 1821 / 979 / 67 / 2998 | 2.22 | 12.889 |

### Validation split (used for selection)

| Model | Precision | Recall | F1 | False-negative rate | TN / FP / FN / TP | Size (MB) | Latency (ms, median) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline: C=1.0 | 0.7249 | 0.9804 | 0.8335 | 0.0196 | 1660 / 1140 / 60 / 3004 | 0.00 | 4.948 |
| improved: max_depth=16 | 0.7416 | 0.9807 | 0.8446 | 0.0193 | 1753 / 1047 / 59 / 3005 | 2.22 | 12.889 |

### All hyperparameter values tried (validation)

| Family | Setting | Threshold | Validation F1 | Recall |
|---|---|---:|---:|---:|
| baseline | C=0.1 | 0.11 | 0.8331 | 0.9804 |
| baseline | C=1.0 | 0.11 | 0.8335 | 0.9804 |
| baseline | C=10.0 | 0.11 | 0.8335 | 0.9804 |
| improved | max_depth=10 | 0.16 | 0.8336 | 0.9804 |
| improved | max_depth=16 | 0.17 | 0.8446 | 0.9807 |

