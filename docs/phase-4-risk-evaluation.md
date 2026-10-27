# Phase 4: Risk Threshold and Local Inference Evaluation

## Purpose

This experiment evaluates classification thresholds for the trained Random Forest risk model and measures local Python inference latency. The evaluation uses held-out synthetic authentication events.

## Threshold evaluation

The following results were measured on the held-out predictions:

| Threshold | Precision | Recall | F1 | False positives | False negatives | False-positive rate | False-negative rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.20 | 0.8605 | 0.8810 | 0.8706 | 84 | 70 | 0.0595 | 0.1190 |
| 0.30 | 0.9259 | 0.8707 | 0.8975 | 41 | 76 | 0.0290 | 0.1293 |
| 0.40 | 0.9445 | 0.8690 | 0.9052 | 30 | 77 | 0.0212 | 0.1310 |
| 0.50 | 0.9605 | 0.8673 | 0.9115 | 21 | 78 | 0.0149 | 0.1327 |
| 0.60 | 0.9844 | 0.8605 | 0.9183 | 8 | 82 | 0.0057 | 0.1395 |
| 0.70 | 0.9881 | 0.8503 | 0.9141 | 6 | 88 | 0.0042 | 0.1497 |
| 0.80 | 0.9938 | 0.8231 | 0.9005 | 3 | 104 | 0.0021 | 0.1769 |

## Interpretation

Increasing the threshold reduces false positives but also reduces recall. At 0.50, precision is 0.9605 and recall is 0.8673, with 21 false positives and 78 false negatives. At 0.60, false positives fall to 8, while false negatives rise to 82. At 0.80, false positives fall to 3, but false negatives increase to 104.

A threshold of 0.50 is retained as the initial experimental operating point. This is a provisional choice, not a universally optimal threshold. The appropriate threshold depends on the relative costs of false positives and false negatives and should be revisited during Phase 6 evaluation.

## Local inference latency

| Measurement | Result |
|---|---:|
| Warm-up runs | 50 |
| Measured inference calls | 1,000 |
| Mean per-call latency | 46.6702 ms |
| P50 latency | 45.5507 ms |
| P95 latency | 55.7182 ms |
| P99 latency | 67.5224 ms |
| Minimum latency | 39.9691 ms |
| Maximum latency | 95.9993 ms |
| Separate model-load measurement | 257.2047 ms |
| Separate scorer-initialization measurement | 116.4183 ms |
| Model file size | 21,029,266 bytes |

## Limitations

- The dataset is synthetic, and its labels and feature distributions reflect the simulation design rather than observed production attacks.
- The reported metrics do not establish real-world detection performance.
- Local latency depends on the machine, Python environment, and loaded model.
- Local timings exclude API Gateway, network latency, AWS Lambda startup, and AWS resource overhead.
- The local inference results are not directly comparable to the existing client-observed JWT baseline.
- Replay attempts were poorly detected by contextual features in the earlier scenario analysis. Deterministic token signature, expiry, invocation binding, and one-time replay checks remain separate security controls; the ML model must not be claimed to replace them.

## Reproducibility

The evaluation script is `experiments/scripts/evaluate_risk_thresholds.py`.

Generated outputs:

- `experiments/results/risk_threshold_metrics.csv`
- `experiments/results/inference_latency_local.json`

The Random Forest model can be regenerated using the existing training script and synthetic dataset generator.

## Project roadmap

- Phase 1: Research and proposal planning — proposal completed; dissertation literature review remains.
- Phase 2: AWS foundation and JWT baseline — established.
- Phase 3: Invocation-bound dynamic tokens — implemented and tested.
- Phase 4: ML risk-score engine — training, inference, threshold evaluation, and local latency measurement completed; integration and testing remain.
- Phase 5: Federated learning — planned, using simulated clients and model updates rather than sharing raw authentication data.
- Phase 6: Integration and benchmarking against the JWT baseline and relevant methods — pending.
- Phase 7: Research analysis and dissertation — pending.
