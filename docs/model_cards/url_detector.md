# Model card: URL phishing detector

- **File:** `models/url_detector.pkl`
- **Selected model:** improved (max_depth=16)
- **Trained:** 2026-11-05
- **Random seed:** 42
- **Labels:** legitimate, phishing (positive class = 1, phishing)
- **Decision threshold:** 0.17
- **Input features:** 85 URL-only features from the Mendeley dataset (ADR-0012)
- **Size on disk:** 2.22 MB (limit 25 MB)
- **Latency on this PC:** 12.889 ms median (limit 15 ms)
- **Constraints:** met

## Performance (test split, reported once)

- Accuracy: 0.8217
- Precision: 0.7538
- Recall: 0.9781
- F1: 0.8515
- False-negative rate (missed threats): 0.0219
- Confusion matrix (TN / FP / FN / TP): 1821 / 979 / 67 / 2998

## Limitations

- Scores come from one fixed split and one seed (no cross-validation).
- Latency is measured on a PC, not on the target Arm phone.
- Public datasets are older than today's threats.
