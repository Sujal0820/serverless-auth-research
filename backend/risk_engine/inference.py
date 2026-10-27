"""Local inference for the synthetic serverless-auth risk model.

This module estimates contextual risk only. It does not authenticate requests,
issue tokens, or replace deterministic token/replay security controls.
"""

from pathlib import Path
from typing import Any, Mapping

import joblib
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "results" / "models" / "risk_random_forest.joblib"

FEATURES = (
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
)


class RiskInferenceError(ValueError):
    """Raised when risk inference input is invalid."""


class RiskScorer:
    """Load a trained model and estimate contextual authentication risk."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        decision_threshold: float = 0.5,
    ) -> None:
        if not 0.0 <= decision_threshold <= 1.0:
            raise ValueError("decision_threshold must be between 0 and 1.")

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Risk model not found: {self.model_path}. "
                "Run the training script first."
            )

        self.model = joblib.load(self.model_path)
        self.decision_threshold = decision_threshold

        expected = tuple(getattr(self.model, "feature_names_in_", ()))
        if expected and expected != FEATURES:
            raise ValueError(
                "Model feature schema does not match inference FEATURES."
            )

        if not hasattr(self.model, "predict_proba"):
            raise TypeError("The configured model must support predict_proba.")

        classes = list(self.model.classes_)
        if 1 not in classes:
            raise ValueError("The model does not contain suspicious class 1.")
        self.suspicious_class_index = classes.index(1)

    def score(self, context: Mapping[str, Any]) -> dict[str, Any]:
        """Return a contextual risk estimate for one event.

        Required keys are the ten numeric model features. Extra keys are
        ignored, so callers must not rely on this method to validate identity,
        token signature, invocation binding, or replay state.
        """
        missing = [feature for feature in FEATURES if feature not in context]
        if missing:
            raise RiskInferenceError(
                f"Missing required features: {', '.join(missing)}"
            )

        row: dict[str, float] = {}
        for feature in FEATURES:
            value = context[feature]
            if isinstance(value, bool):
                raise RiskInferenceError(
                    f"Feature '{feature}' must be numeric, not boolean."
                )
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise RiskInferenceError(
                    f"Feature '{feature}' must be numeric."
                ) from exc

            if not pd.notna(numeric_value) or numeric_value in (
                float("inf"), float("-inf")
            ):
                raise RiskInferenceError(
                    f"Feature '{feature}' must be finite."
                )
            row[feature] = numeric_value

        frame = pd.DataFrame([row], columns=FEATURES)
        probabilities = self.model.predict_proba(frame)[0]
        probability = float(probabilities[self.suspicious_class_index])
        risk_score = round(probability * 100.0, 2)

        if probability >= 0.75:
            risk_level = "HIGH"
        elif probability >= 0.40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "risk_score": risk_score,
            "risk_probability": round(probability, 6),
            "risk_level": risk_level,
            "predicted_suspicious": probability >= self.decision_threshold,
            "decision_threshold": self.decision_threshold,
            "model": "random_forest",
            "model_source": "synthetic_research_dataset",
        }
