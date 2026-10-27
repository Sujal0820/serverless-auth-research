"""Train and evaluate baseline ML models on synthetic auth events.

This experiment measures performance on simulated data, not real-world attacks.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "datasets" / "synthetic" / "authentication_events.csv"
RESULTS_DIR = ROOT / "experiments" / "results"
MODEL_DIR = ROOT / "results" / "models"
SEED = 42
TEST_SIZE = 0.20

FEATURES = [
    "request_hour_utc",
    "hour_deviation",
    "device_familiarity",
    "location_deviation_km",
    "network_reputation",
    "invocations_last_5m",
    "invocation_rate_deviation",
    "function_pattern_deviation",
    "failed_auth_attempts_10m",
    "token_age_seconds",
]


def build_models():
    return {
        "dummy_most_frequent": Pipeline(
            [("imputer", SimpleImputer(strategy="median")),
             ("model", DummyClassifier(strategy="most_frequent"))]
        ),
        "logistic_regression": Pipeline(
            [("imputer", SimpleImputer(strategy="median")),
             ("scaler", StandardScaler()),
             ("model", LogisticRegression(
                 max_iter=2000, class_weight="balanced", random_state=SEED
             ))]
        ),
        "random_forest": Pipeline(
            [("imputer", SimpleImputer(strategy="median")),
             ("model", RandomForestClassifier(
                 n_estimators=300,
                 min_samples_leaf=2,
                 class_weight="balanced",
                 random_state=SEED,
                 n_jobs=-1,
             ))]
        ),
    }


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    required = set(FEATURES + ["is_suspicious"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {sorted(missing)}")

    X = df[FEATURES].replace([np.inf, -np.inf], np.nan)
    y = df["is_suspicious"].astype(int)

    if set(y.unique()) != {0, 1}:
        raise ValueError("Expected both binary labels 0 and 1.")

    X_train, X_test, y_train, y_test, train_idx, test_idx = train_test_split(
        X,
        y,
        df.index,
        test_size=TEST_SIZE,
        random_state=SEED,
        stratify=y,
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    metrics = []
    prediction_frames = []
    fitted_models = {}

    for name, model in build_models().items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)

        if hasattr(model, "predict_proba"):
            probability = model.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, probability)
        else:
            probability = np.zeros(len(y_test))
            auc = float("nan")

        tn, fp, fn, tp = confusion_matrix(
            y_test, pred, labels=[0, 1]
        ).ravel()

        metrics.append({
            "model": name,
            "dataset_rows": len(df),
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "seed": SEED,
            "features": "|".join(FEATURES),
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred, zero_division=0),
            "recall": recall_score(y_test, pred, zero_division=0),
            "f1": f1_score(y_test, pred, zero_division=0),
            "roc_auc": auc,
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
            "sklearn_version": sklearn.__version__,
        })

        prediction_frames.append(pd.DataFrame({
            "row_index": test_idx.to_numpy(),
            "scenario": df.loc[test_idx, "scenario"].to_numpy(),
            "y_true": y_test.to_numpy(),
            "model": name,
            "y_pred": pred,
            "risk_probability": probability,
        }))

        fitted_models[name] = model

    metrics_df = pd.DataFrame(metrics)
    metrics_path = RESULTS_DIR / "risk_model_metrics.csv"
    predictions_path = RESULTS_DIR / "risk_model_predictions.csv"
    report_path = RESULTS_DIR / "risk_model_report.json"

    metrics_df.to_csv(metrics_path, index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(
        predictions_path, index=False
    )

    # Save the Random Forest pipeline for later inference integration.
    joblib.dump(
        fitted_models["random_forest"],
        MODEL_DIR / "risk_random_forest.joblib",
    )

    report = {
        "dataset": str(DATA_PATH.relative_to(ROOT)),
        "rows": len(df),
        "class_counts": {
            str(k): int(v) for k, v in y.value_counts().sort_index().items()
        },
        "features": FEATURES,
        "excluded_columns": [
            "event_id", "scenario", "replay_signal", "token_integrity_signal"
        ],
        "seed": SEED,
        "test_size": TEST_SIZE,
        "sklearn_version": sklearn.__version__,
        "metrics": metrics,
        "limitations": [
            "Labels are derived from synthetic scenarios.",
            "Performance does not establish real-world attack-detection accuracy.",
            "The random split may place similar simulated patterns in train and test.",
            "Scenario-wise results should be reviewed for generalisation weaknesses.",
        ],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== SYNTHETIC RISK MODEL EVALUATION ===")
    print(f"Dataset rows: {len(df)}")
    print(f"Training rows: {len(X_train)}")
    print(f"Test rows: {len(X_test)}")
    print(f"Features: {len(FEATURES)}")
    print(f"scikit-learn: {sklearn.__version__}")
    print("\nMetrics:")
    print(metrics_df[
        ["model", "accuracy", "precision", "recall", "f1", "roc_auc",
         "false_positive", "false_negative"]
    ].round(4).to_string(index=False))
    print("\nSaved:")
    print(metrics_path)
    print(predictions_path)
    print(report_path)
    print(MODEL_DIR / "risk_random_forest.joblib")


if __name__ == "__main__":
    main()
