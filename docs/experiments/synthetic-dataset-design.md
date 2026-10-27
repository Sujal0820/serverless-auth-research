# Synthetic Authentication Dataset Design

## Purpose

This document records the design of the initial synthetic dataset for the
Federated Risk-Aware Invocation-Bound Token Authentication Framework.

## Dataset

- File: `datasets/synthetic/authentication_events.csv`
- Rows: 10,000
- Generator: `experiments/scripts/generate_synthetic_dataset.py`
- Random seed: 42
- Label: `is_suspicious` (0 = normal; 1 = simulated suspicious event)
- Data source: synthetic simulation; no real user or production telemetry.

## Simulated scenarios

The generator samples these scenario categories using configured probabilities:

- Normal authentication activity
- Unusual location
- Unfamiliar device
- Invocation anomaly
- Replay attempt
- Token abuse

The scenario column is metadata for evaluation and analysis. It must not be
used as a model input.

## Initial context-only model features

The first model evaluation will consider:

- `request_hour_utc`
- `hour_deviation`
- `device_familiarity`
- `location_deviation_km`
- `network_reputation`
- `invocations_last_5m`
- `invocation_rate_deviation`
- `function_pattern_deviation`
- `failed_auth_attempts_10m`
- `token_age_seconds`

`event_id` is a row identifier, not a predictive feature.

`replay_signal` and `token_integrity_signal` are excluded from the primary
model because they directly encode specific simulated attack mechanisms.
Replay detection and cryptographic integrity validation should remain explicit
security controls rather than being delegated to a statistical classifier.

## Label construction and leakage risk

The binary label is derived directly from the scenario selected by the
synthetic generator. Consequently, the task measures how well a model learns
the simulator's scenario patterns. It does not establish real-world attack
detection accuracy.

Some context features are deliberately shifted for particular scenarios.
Model performance may therefore be optimistic relative to real deployment.
The evaluation must report class-wise precision, recall, F1, confusion matrix,
and ROC-AUC where applicable, and must compare against a simple baseline.

## Dataset validation

The initial generation produced 10,000 rows, with 7,058 normal and 2,942
suspicious events. Validation found no missing values, duplicate rows, or
duplicate event IDs.

The observed class balance follows the configured simulation proportions and
must not be interpreted as the prevalence of suspicious traffic in production.

## Reproducibility

The generator's default seed is 42. Preserve the generator, dataset, feature
selection, model configuration, and evaluation outputs together so the
experiment can be reproduced. Record any later dataset or feature changes.

## Initial Model Evaluation: Replay Limitation

The initial experiment used a stratified 80/20 train/test split with random
seed 42. On the 2,000-event test set, the Random Forest achieved 95.05%
accuracy, 96.05% precision, 86.73% recall, an F1 score of 0.9115, and ROC-AUC
of 0.9379. These results apply only to the current synthetic dataset.

Scenario-level evaluation revealed that the model detected only 1 of 73
replay-attempt events in the test set. A comparison of the ten context-only
features showed similar means and standard deviations for normal and replay
events. This is consistent with the generator design: replay attempts do not
currently introduce a distinguishable contextual feature pattern.

### Architectural decision

The ML model will assess contextual authentication risk. Replay prevention
will remain a deterministic security control implemented by invocation-bound
dynamic-token validation and one-time `jti` consumption in DynamoDB. The model
must not be used as a substitute for signature, expiry, subject, invocation
binding, or replay checks.

The initial results must not be presented as evidence of real-world replay
detection. Future experiments may investigate additional observable signals,
but any new signal must be justified by the system design and evaluated
without leaking the target label.

### Evaluation caveats

The dataset labels are derived from the simulator's scenario categories.
Performance can therefore reflect the simulated feature distributions rather
than generalisation to real attacks. Scenario-wise metrics and error counts
should accompany aggregate metrics in subsequent evaluation.
