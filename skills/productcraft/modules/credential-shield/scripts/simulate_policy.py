#!/usr/bin/env python3
"""Offline synthetic signal demonstration, NOT production authentication code.

This model deliberately has no storage, network, TLS access or decision gateway.
It illustrates how a distributed campaign may become visible through *combined*
account, source, cohort and failure signals. All identifiers are synthetic.
Real services require windowed atomic bounded counters, tuned thresholds,
privacy controls, trusted signal provenance and false-positive evaluation.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Attempt:
    target: str
    source: str
    failed: bool
    cohort: str | None = None  # synthetic, not a trusted fingerprint


class OfflineSignalModel:
    """Finite-batch aggregation for teaching; never use in request middleware."""

    def __init__(self) -> None:
        self.attempts_by_target: Counter[str] = Counter()
        self.failed_by_target: Counter[str] = Counter()
        self.sources_by_target: dict[str, set[str]] = defaultdict(set)
        self.targets_by_source: dict[str, set[str]] = defaultdict(set)
        self.attempts_by_cohort: Counter[str] = Counter()
        self.failed_by_cohort: Counter[str] = Counter()
        self.targets_by_cohort: dict[str, set[str]] = defaultdict(set)
        self.sources_by_cohort: dict[str, set[str]] = defaultdict(set)
        self.source_attempts: Counter[str] = Counter()

    def observe(self, event: Attempt) -> None:
        self.attempts_by_target[event.target] += 1
        self.source_attempts[event.source] += 1
        self.sources_by_target[event.target].add(event.source)
        self.targets_by_source[event.source].add(event.target)
        if event.failed:
            self.failed_by_target[event.target] += 1
        if event.cohort is not None:
            self.attempts_by_cohort[event.cohort] += 1
            self.targets_by_cohort[event.cohort].add(event.target)
            self.sources_by_cohort[event.cohort].add(event.source)
            if event.failed:
                self.failed_by_cohort[event.cohort] += 1

    def findings(self) -> dict:
        # Arbitrary illustrative thresholds are NOT production configuration.
        per_account = [
            target for target, failures in self.failed_by_target.items()
            if failures >= 10 and len(self.sources_by_target[target]) >= 5
        ]
        sprayed_cohorts = [
            cohort for cohort, attempts in self.attempts_by_cohort.items()
            if attempts >= 100
            and self.failed_by_cohort[cohort] / attempts >= 0.98
            and len(self.targets_by_cohort[cohort]) >= 50
            and len(self.sources_by_cohort[cohort]) >= 25
        ]
        return {
            "per_account_distributed_failure_targets": len(per_account),
            "high_failure_multi_account_cohorts": sorted(sprayed_cohorts),
            "unique_sources": len(self.source_attempts),
            "max_attempts_per_source": max(self.source_attempts.values(), default=0),
            "note": "Observable signals, not instructions to block, lock accounts, or identify users",
        }


def build_scenario(name: str) -> OfflineSignalModel:
    model = OfflineSignalModel()
    if name == "distributed":
        # One failed attempt per source, 200 target IDs, with corroborating cohort.
        for n in range(30_000):
            model.observe(Attempt(f"synthetic-user-{n % 200}", f"synthetic-ip-{n}", True, "cohort-a"))
    elif name == "spray":
        for n in range(3_000):
            model.observe(Attempt(f"synthetic-user-{n}", f"synthetic-ip-{n}", True, "cohort-b"))
    elif name == "shared-network":
        for n in range(800):
            model.observe(Attempt(f"real-user-{n}", "shared-corporate-nat", False, "mainstream-browser"))
    elif name == "shared-fingerprint":
        for n in range(800):
            model.observe(Attempt(f"real-user-{n}", f"synthetic-ip-{n}", False, "common-browser"))
    else:
        raise ValueError(f"Unknown scenario: {name}")
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=["distributed", "spray", "shared-network", "shared-fingerprint", "all"],
        default="all",
    )
    args = parser.parse_args()
    scenarios = (
        ["distributed", "spray", "shared-network", "shared-fingerprint"]
        if args.scenario == "all" else [args.scenario]
    )
    results = {name: build_scenario(name).findings() for name in scenarios}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
