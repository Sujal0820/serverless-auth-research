"""Evaluate risk thresholds and local inference latency.

Threshold metrics use the held-out Random Forest predictions.
Latency is local Python inference latency, not AWS Lambda latency.
"""

import json
import statistics
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PREDICTIONS_PATH = ROOT / "experiments" / "results" / "risk_model_predictions.csv"
MODEL_PATH = ROOT / "results" / "models" / "risk_random_forest.joblib"
THRESHOLD_OUTPUT = ROOT / "experiments" / "results" / "risk_threshold_metrics.csv"
LATENCY_OUTPUT = ROOT / "experiments" / "results" / "inference_latency_local.json"

THRESHOLDS = [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
WARMUP_RUNS = 50
MEASURED_RUNS = 1000

SAMPLE_CONTEXT = {
    "request_hour_utc": 12,
    "hour_deviation": 2,
    "device_familiarity": 0.8,
    "location_deviation_km": 5,
    "network_reputation": 0.9,
    "invocations_last_5m": 3,
    "invocation_rate_deviation": 1,
    "function_pattern_deviation": 0.2,
    "failed_auth_attempts_10m": 0,
    "token_age_seconds": 10,
}


def evaluate_thresholds() -> pd.DataFrame:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(PREDICTIONS_PATH)

    df = pd.read_csv(PREDICTIONS_PATH)
    df = df[df["model"] == "random_forest"].copy()

    if df.empty:
        raise ValueError("No Random Forest predictions found.")

    y_true = df["y_true"].astype(int).to_numpy()
    probabilities = df["risk_probability"].astype(float).to_numpy()

    if not np.isfinite(probabilities).all():
        raise ValueError("Prediction probabilities contain non-finite values.")

    rows = []
    for threshold in THRESHOLDS:
        y_pred = (probabilities >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(
            y_true, y_pred, labels=[0, 1]
        ).ravel()

        rows.append({
            "threshold": threshold,
            "test_events": len(y_true),
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
            "false_positive_rate": fp / (fp + tn) if (fp + tn) else 0.0,
            "false_negative_rate": fn / (fn + tp) if (fn + tp) else 0.0,
        })

    result = pd.DataFrame(rows)
    result.to_csv(THRESHOLD_OUTPUT, index=False)
    return result


def benchmark_local_inference() -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"{MODEL_PATH} not found. Run the training script first."
        )

    # Include model load time as a separate cold-load measurement.
    load_start = time.perf_counter()
    model = joblib.load(MODEL_PATH)
    model_load_ms = (time.perf_counter() - load_start) * 1000

    from backend.risk_engine.inference import RiskScorer

    # Measure the public inference wrapper, loading its own model once.
    scorer_load_start = time.perf_counter()
    scorer = RiskScorer(model_path=MODEL_PATH)
    scorer_initialization_ms = (
        time.perf_counter() - scorer_load_start
    ) * 1000

    for _ in range(WARMUP_RUNS):
        scorer.score(SAMPLE_CONTEXT)

    samples_ms = []
    for _ in range(MEASURED_RUNS):
        start = time.perf_counter()
        scorer.score(SAMPLE_CONTEXT)
        samples_ms.append((time.perf_counter() - start) * 1000)

    samples_ms.sort()
    result = {
        "measurement_scope": "local Python inference wrapper; not AWS Lambda",
        "model_path": str(MODEL_PATH.relative_to(ROOT)),
        "warmup_runs": WARMUP_RUNS,
        "measured_runs": MEASURED_RUNS,
        "model_file_size_bytes": MODEL_PATH.stat().st_size,
        "model_load_ms_separate_measurement": round(model_load_ms, 4),
        "scorer_initialization_ms_separate_measurement": round(
            scorer_initialization_ms, 4
        ),
        "per_call_latency_ms": {
            "mean": round(statistics.mean(samples_ms), 4),
            "p50": round(float(np.percentile(samples_ms, 50)), 4),
            "p95": round(float(np.percentile(samples_ms, 95)), 4),
            "p99": round(float(np.percentile(samples_ms, 99)), 4),
            "min": round(min(samples_ms), 4),
            "max": round(max(samples_ms), 4),
        },
        "limitations": [
            "Local measurements depend on this machine and Python environment.",
            "They exclude API Gateway, network, Lambda startup, and AWS resource overhead.",
            "They are not directly comparable to client-observed JWT baseline latency.",
        ],
    }

    LATENCY_OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    threshold_df = evaluate_thresholds()
    latency = benchmark_local_inference()

    print("=== THRESHOLD EVALUATION ===")
    print(threshold_df[
        ["threshold", "precision", "recall", "f1",
         "false_positive", "false_negative",
         "false_positive_rate", "false_negative_rate"]
    ].round(4).to_string(index=False))

    print("\n=== LOCAL INFERENCE LATENCY ===")
    print(json.dumps(latency, indent=2))

    print("\nSaved:")
    print(THRESHOLD_OUTPUT)
    print(LATENCY_OUTPUT)


if __name__ == "__main__":
    main()
