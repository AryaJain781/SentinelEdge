# Model card: Network intrusion detector

- **File:** `models/network_detector.pkl`
- **Selected model:** baseline (C=1.0)
- **Trained:** 2026-11-05
- **Random seed:** 42
- **Labels:** normal, attack (positive class = 1, attack)
- **Decision threshold:** 0.50
- **Input features:** 41 NSL-KDD fields (3 text fields one-hot encoded)
- **Size on disk:** 0.01 MB (limit 25 MB)
- **Latency on this PC:** 7.804 ms median (limit 15 ms)
- **Constraints:** met

## Performance (test split, reported once)

- Accuracy: 0.9695
- Precision: 0.9768
- Recall: 0.9572
- F1: 0.9669
- False-negative rate (missed threats): 0.0428
- Confusion matrix (TN / FP / FN / TP): 6602 / 133 / 251 / 5612

## Limitations

- Scores come from one fixed split and one seed (no cross-validation).
- Latency is measured on a PC, not on the target Arm phone.
- Public datasets are older than today's threats.
