"""Run: python -m unittest tests.test_policy -v   (offline; synthetic data only)"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from policy import (contexts, direct_policy, fixed_policy, leave_source_out, planted_best_arm,  # noqa: E402
                    reward_table, synthetic, thompson_replay, value, cv_rewards)


class PolicyCase(unittest.TestCase):
    def test_oracle_policy_recovers_planted_best_arm(self):
        R, X, _ = synthetic(200, seed=0)
        pol = direct_policy(R, X, depth=2)
        learned = value(pol, R, X)
        oracle = float(R.max(axis=1).mean())            # per-source max of realised rewards
        self.assertGreaterEqual(learned, oracle - 0.05)
        for arm in R.columns:
            self.assertGreater(learned, value(fixed_policy(arm), R, X), arm)
        self.assertGreaterEqual((pol.assign(X) == planted_best_arm(X)).mean(), 0.95)

    def test_leave_source_out_no_leak(self):
        R, X, _ = synthetic(200, seed=1)
        in_sample = value(direct_policy(R, X), R, X)
        held_out = cv_rewards(R, X, folds=10)["learned"].mean()
        self.assertLessEqual(held_out, in_sample + 1e-12)
        # pure noise: nothing to learn, so the CV policy must not beat the best fixed arm beyond CI noise
        rng = np.random.default_rng(3)
        Rn = pd.DataFrame((rng.random(R.shape) < 0.5).astype(float), index=R.index, columns=R.columns)
        noise_in = value(direct_policy(Rn, X), Rn, X)
        res = leave_source_out(Rn, X, n_boot=500).set_index("name")
        self.assertLessEqual(res.loc["learned", "estimate"], noise_in + 1e-12)
        d = res.loc["learned - best_single"]
        self.assertLessEqual(d["ci_lo"], 0.0)
        # real structure: the learned policy is clearly ahead of every comparator
        real = leave_source_out(R, X, n_boot=500).set_index("name")
        for c in ("learned - best_single", "learned - always_ai", "learned - never_ai"):
            self.assertGreater(real.loc[c, "ci_lo"], 0.0, c)

    def test_thompson_regret_sublinear_on_synthetic(self):
        R, X, _ = synthetic(200, seed=0)
        reg = thompson_replay(R, X, n_orders=200).set_index("n_sources")
        n = len(R)
        self.assertEqual(int(reg.index[-1]), n)
        self.assertLess(reg.loc[n, "regret_mean"] / reg.loc[50, "regret_mean"], n / 50)
        self.assertLess(reg.loc[n, "per_step_mean"], reg.loc[50, "per_step_mean"])

    def test_reward_table_repair_arm_uses_repaired_outcome(self):
        key = pd.DataFrame([
            ("o1", "s1", "gen", "chunked", False, ""), ("o2", "s2", "gen", "chunked", False, ""),
            ("o3", "s1", "deterministic", "chunked", False, ""), ("o4", "s2", "deterministic", "chunked", False, ""),
            ("o1|repair1", "s1", "gen", "chunked", True, "o1"),
        ], columns=["output_id", "source_id", "generator", "transformation", "is_repair", "repair_of"])
        lab = pd.DataFrame({"output_id": ["o1", "o2", "o3", "o4", "o1|repair1"],
                            "SAFE_AND_USEFUL": [0, 1, 1, 0, 1]})
        R = reward_table(lab, key, {"o1": 0.10, "o1|repair1": 0.05, "o2": 0.10}, lam_cost=1.0)
        self.assertEqual(list(R.columns), ["deterministic", "gen:chunked", "gen:chunked+repair"])
        self.assertAlmostEqual(R.loc["s1", "gen:chunked"], 0 - 0.10)
        self.assertAlmostEqual(R.loc["s1", "gen:chunked+repair"], 1 - 0.15)   # repaired outcome, both costs
        self.assertAlmostEqual(R.loc["s2", "gen:chunked+repair"], 1 - 0.10)   # no repair: original's outcome
        self.assertAlmostEqual(R.loc["s1", "deterministic"], 1.0)             # missing cost counts as 0
        # a missing arm is NaN and falls back to deterministic in value()
        R2 = R.copy()
        R2.loc["s2", "gen:chunked"] = np.nan
        X = contexts([{"source_id": s, "text": "Tom has 3 apples."} for s in R2.index])
        self.assertAlmostEqual(value(fixed_policy("gen:chunked"), R2, X), (R2.loc["s1", "gen:chunked"] + 0.0) / 2)

    def test_policy_describe_readable(self):
        R, X, _ = synthetic(200, seed=0)
        text = direct_policy(R, X).describe()
        for needle in ("deterministic", "gen-a:chunked", "gen-b:plain", "length=len_low", "comparison", "IF "):
            self.assertIn(needle, text)
        self.assertEqual(fixed_policy("deterministic").describe(), "ALWAYS use deterministic")

    def test_contexts_handle_missing_n_steps(self):
        X = contexts([{"source_id": "a", "text": "Ann has 5 dollars and 20% more.", "n_steps": 3},
                      {"source_id": "b", "text": "Bob runs for two hours.", "n_steps": None},
                      {"source_id": "c", "text": "Cy has twice as many apples as 4 friends have together here."}])
        self.assertEqual(list(X["step_bucket"]), ["s=3", "unknown", "unknown"])
        self.assertTrue(X.loc["a", "percent"] and X.loc["a", "money"] and X.loc["c", "comparison"])
        self.assertEqual(set(X["length"]), {"len_low", "len_mid", "len_high"})


if __name__ == "__main__":
    unittest.main()
