import unittest

from backend.risk_engine.inference import (
    FEATURES,
    RiskInferenceError,
    RiskScorer,
)


def valid_context():
    return {
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


class RiskInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = RiskScorer()

    def test_valid_context_returns_risk_result(self):
        result = self.scorer.score(valid_context())

        self.assertGreaterEqual(result["risk_score"], 0)
        self.assertLessEqual(result["risk_score"], 100)
        self.assertGreaterEqual(result["risk_probability"], 0)
        self.assertLessEqual(result["risk_probability"], 1)
        self.assertIn(result["risk_level"], {"LOW", "MEDIUM", "HIGH"})
        self.assertIsInstance(result["predicted_suspicious"], bool)

    def test_result_contains_model_metadata(self):
        result = self.scorer.score(valid_context())

        self.assertEqual(result["model"], "random_forest")
        self.assertEqual(
            result["model_source"], "synthetic_research_dataset"
        )

    def test_missing_feature_is_rejected(self):
        context = valid_context()
        context.pop(FEATURES[0])

        with self.assertRaises(RiskInferenceError):
            self.scorer.score(context)

    def test_non_numeric_feature_is_rejected(self):
        context = valid_context()
        context["device_familiarity"] = "not-a-number"

        with self.assertRaises(RiskInferenceError):
            self.scorer.score(context)

    def test_nan_is_rejected(self):
        context = valid_context()
        context["network_reputation"] = float("nan")

        with self.assertRaises(RiskInferenceError):
            self.scorer.score(context)

    def test_infinity_is_rejected(self):
        context = valid_context()
        context["location_deviation_km"] = float("inf")

        with self.assertRaises(RiskInferenceError):
            self.scorer.score(context)

    def test_boolean_is_not_accepted_as_numeric(self):
        context = valid_context()
        context["request_hour_utc"] = True

        with self.assertRaises(RiskInferenceError):
            self.scorer.score(context)

    def test_threshold_must_be_valid(self):
        with self.assertRaises(ValueError):
            RiskScorer(decision_threshold=1.5)


if __name__ == "__main__":
    unittest.main()
