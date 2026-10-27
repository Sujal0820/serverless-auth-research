"""Generate a reproducible synthetic dataset for serverless auth research.

Synthetic data only. It contains no real user identifiers, IP addresses,
credentials, tokens, or production telemetry.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "datasets" / "synthetic" / "authentication_events.csv"

SCENARIO_WEIGHTS = {
    "normal": 0.70,
    "unusual_location": 0.08,
    "unfamiliar_device": 0.07,
    "invocation_anomaly": 0.07,
    "replay_attempt": 0.04,
    "token_abuse": 0.04,
}


def generate_dataset(rows: int, seed: int) -> pd.DataFrame:
    """Generate synthetic events with explicit scenario-derived labels."""
    if rows < 100:
        raise ValueError("rows must be at least 100 for useful evaluation.")

    rng = np.random.default_rng(seed)

    scenarios = rng.choice(
        list(SCENARIO_WEIGHTS),
        size=rows,
        p=list(SCENARIO_WEIGHTS.values()),
    )
    suspicious = scenarios != "normal"

    # Features represent context that a risk scorer could receive.
    # All values are synthetic and generated independently of real identities.
    hour = rng.integers(0, 24, size=rows)
    usual_hour = rng.integers(7, 23, size=rows)
    hour_deviation = np.abs(hour - usual_hour)
    hour_deviation = np.minimum(hour_deviation, 24 - hour_deviation)

    device_familiarity = rng.beta(8, 2, size=rows)
    location_deviation_km = rng.gamma(2, 8, size=rows)
    network_reputation = rng.beta(8, 2, size=rows)
    invocations_last_5m = rng.poisson(3, size=rows)
    normal_invocation_rate = rng.poisson(3, size=rows)
    invocation_rate_deviation = np.abs(
        invocations_last_5m - normal_invocation_rate
    )
    function_pattern_deviation = rng.beta(2, 8, size=rows)
    failed_auth_attempts_10m = rng.poisson(0.15, size=rows)
    token_age_seconds = rng.integers(0, 31, size=rows)
    replay_signal = np.zeros(rows, dtype=int)
    token_integrity_signal = np.zeros(rows, dtype=int)

    # Scenario mechanisms simulate plausible observable differences.
    # They are not intended to represent all real-world attack behaviour.
    for scenario in SCENARIO_WEIGHTS:
        idx = np.flatnonzero(scenarios == scenario)
        count = len(idx)

        if scenario == "unusual_location":
            location_deviation_km[idx] = rng.gamma(8, 45, size=count)
            network_reputation[idx] = rng.beta(3, 5, size=count)

        elif scenario == "unfamiliar_device":
            device_familiarity[idx] = rng.beta(2, 8, size=count)

        elif scenario == "invocation_anomaly":
            invocations_last_5m[idx] = rng.poisson(18, size=count)
            invocation_rate_deviation[idx] = rng.integers(8, 30, size=count)
            function_pattern_deviation[idx] = rng.beta(7, 2, size=count)

        elif scenario == "replay_attempt":
            replay_signal[idx] = 1
            token_age_seconds[idx] = rng.integers(0, 31, size=count)

        elif scenario == "token_abuse":
            token_integrity_signal[idx] = 1
            failed_auth_attempts_10m[idx] = rng.poisson(3, size=count)
            network_reputation[idx] = rng.beta(2, 6, size=count)

    df = pd.DataFrame(
        {
            "event_id": [f"synthetic-{i:06d}" for i in range(rows)],
            "request_hour_utc": hour,
            "hour_deviation": hour_deviation,
            "device_familiarity": np.round(device_familiarity, 4),
            "location_deviation_km": np.round(location_deviation_km, 3),
            "network_reputation": np.round(network_reputation, 4),
            "invocations_last_5m": invocations_last_5m,
            "invocation_rate_deviation": invocation_rate_deviation,
            "function_pattern_deviation": np.round(
                function_pattern_deviation, 4
            ),
            "failed_auth_attempts_10m": failed_auth_attempts_10m,
            "token_age_seconds": token_age_seconds,
            "replay_signal": replay_signal,
            "token_integrity_signal": token_integrity_signal,
            "scenario": scenarios,
            "is_suspicious": suspicious.astype(int),
        }
    )

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    df = generate_dataset(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    print(f"Output: {args.output}")
    print(f"Rows: {len(df)}")
    print(f"Seed: {args.seed}")
    print(f"Suspicious rate: {df['is_suspicious'].mean():.3f}")
    print("\nScenario counts:")
    print(df["scenario"].value_counts().sort_index().to_string())
    print("\nLabel counts:")
    print(df["is_suspicious"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
