"""
Sample data/AI workflow script for testing Ravel.

Simulates:
1) Extract + clean
2) Feature generation
3) Embedding-style computation
4) Aggregate metrics

This is intentionally CPU-only and deterministic, but has enough work
and logging to look like a real pipeline job.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import random
import statistics
import time


def _seed_all(seed: int) -> None:
    random.seed(seed)


def _hash_to_float(text: str) -> float:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def extract_records(count: int) -> list[str]:
    base = [f"user_{i}" for i in range(count)]
    return base


def clean_records(records: list[str]) -> list[str]:
    cleaned = []
    for r in records:
        if "_" in r and len(r) > 3:
            cleaned.append(r.strip().lower())
    return cleaned


def generate_features(records: list[str], dim: int) -> list[list[float]]:
    features: list[list[float]] = []
    for r in records:
        row = [(_hash_to_float(f"{r}:{i}") * 2.0 - 1.0) for i in range(dim)]
        features.append(row)
    return features


def embed_features(features: list[list[float]]) -> list[float]:
    # Lightweight "embedding" using norms; intentionally a little heavy.
    outputs = []
    for row in features:
        norm = math.sqrt(sum(v * v for v in row))
        outputs.append(norm)
    return outputs


def aggregate_metrics(values: list[float]) -> dict[str, float]:
    return {
        "count": float(len(values)),
        "mean": statistics.mean(values) if values else 0.0,
        "p50": statistics.median(values) if values else 0.0,
        "p90": statistics.quantiles(values, n=10)[-1] if len(values) >= 10 else 0.0,
        "max": max(values) if values else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Feature pipeline demo for Ravel")
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--dim", type=int, default=64)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    _seed_all(args.seed)

    print("[1/4] Extracting records...")
    records = extract_records(args.rows)
    time.sleep(args.sleep)

    print("[2/4] Cleaning records...")
    cleaned = clean_records(records)
    time.sleep(args.sleep)

    print("[3/4] Generating features...")
    features = generate_features(cleaned, args.dim)
    time.sleep(args.sleep)

    print("[4/4] Embedding + aggregating...")
    embedded = embed_features(features)
    metrics = aggregate_metrics(embedded)

    print("\nMetrics")
    for key, value in metrics.items():
        print(f"- {key}: {value:.4f}")


if __name__ == "__main__":
    main()
