# Model card: SMS scam detector

- **File:** `models/sms_detector.pkl`
- **Selected model:** baseline (alpha=0.1)
- **Trained:** 2026-11-05
- **Random seed:** 42
- **Labels:** ham, spam (positive class = 1, spam)
- **Decision threshold:** 0.50
- **Input features:** `text_clean` (TF-IDF, 1-2 grams) plus 8 metadata counts
- **Size on disk:** 0.51 MB (limit 25 MB)
- **Latency on this PC:** 3.970 ms median (limit 15 ms)
- **Constraints:** met

## Performance (test split, reported once)

- Accuracy: 0.9857
- Precision: 0.9855
- Recall: 0.9067
- F1: 0.9444
- False-negative rate (missed threats): 0.0933
- Confusion matrix (TN / FP / FN / TP): 482 / 1 / 7 / 68

## Limitations

- Scores come from one fixed split and one seed (no cross-validation).
- Latency is measured on a PC, not on the target Arm phone.
- Public datasets are older than today's threats.
