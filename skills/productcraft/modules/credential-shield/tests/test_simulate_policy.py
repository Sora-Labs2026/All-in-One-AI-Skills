"""Offline simulator tests. These do NOT prove the host app is protected."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from simulate_policy import Attempt, OfflineSignalModel, build_scenario  # noqa: E402


class SimulatorTests(unittest.TestCase):
    def test_thirty_thousand_ips_are_not_individually_rate_limited(self):
        result = build_scenario("distributed").findings()
        self.assertEqual(result["unique_sources"], 30_000)
        self.assertEqual(result["max_attempts_per_source"], 1)
        self.assertEqual(result["per_account_distributed_failure_targets"], 200)
        self.assertEqual(result["high_failure_multi_account_cohorts"], ["cohort-a"])

    def test_wide_low_frequency_password_spray(self):
        result = build_scenario("spray").findings()
        self.assertEqual(result["per_account_distributed_failure_targets"], 0)
        self.assertEqual(result["high_failure_multi_account_cohorts"], ["cohort-b"])

    def test_shared_nat_is_not_enough_to_flag_attack(self):
        result = build_scenario("shared-network").findings()
        self.assertEqual(result["high_failure_multi_account_cohorts"], [])
        self.assertEqual(result["per_account_distributed_failure_targets"], 0)

    def test_shared_browser_cohort_is_not_enough(self):
        result = build_scenario("shared-fingerprint").findings()
        self.assertEqual(result["high_failure_multi_account_cohorts"], [])

    def test_untrusted_optional_cohort_not_required_for_account_correlation(self):
        m = OfflineSignalModel()
        for i in range(12):
            m.observe(Attempt("one-target", f"ip-{i}", True))
        result = m.findings()
        self.assertEqual(result["per_account_distributed_failure_targets"], 1)
        self.assertEqual(result["high_failure_multi_account_cohorts"], [])


if __name__ == "__main__":
    unittest.main()
