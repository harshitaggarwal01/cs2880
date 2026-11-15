"""Run: python -m unittest tests.test_policy_online -v   (offline; synthetic data only)"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from policy import synthetic  # noqa: E402
from policy_online import (best_arm_per_cell, cell_codes, check_ope, load_feedback, log_feedback,  # noqa: E402
                           ope_estimates, propensities_epsilon, regret_table, replay, simulate_log, to_unit,
                           true_value)

CELLS = ["length", "comparison"]


class OnlineBanditCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R, cls.X, _ = synthetic(400, seed=0)
        cls.res = replay(cls.R, cls.X, n_orders=20, cell_cols=CELLS, seed=1)
        cls.tab = regret_table(cls.res).set_index(["algorithm", "t"])

    def test_thompson_regret_sublinear(self):
        d = self.res["thompson"]["vs_oracle"].mean(axis=0)
        T = len(d)
        self.assertLess(d[-1] - d[T // 2 - 1], d[T // 2 - 1])       # second half adds less than the first
        T = self.tab.loc["thompson"].index.max()
        for other in ("uniform", "eps_greedy"):
            self.assertLess(self.tab.loc[("thompson", T), "regret_vs_oracle"],
                            self.tab.loc[(other, T), "regret_vs_oracle"], other)

    def test_linucb_beats_uniform_and_percentiles_ordered(self):
        T = self.tab.loc["linucb"].index.max()
        self.assertLess(self.tab.loc[("linucb", T), "regret_vs_oracle"], self.tab.loc[("uniform", T), "regret_vs_oracle"])
        for (a, t), row in self.tab.iterrows():
            self.assertLessEqual(row["vs_oracle_lo"], row["regret_vs_oracle"] + 1e-9)
            self.assertGreaterEqual(row["vs_oracle_hi"], row["regret_vs_oracle"] - 1e-9)

    def test_unit_rescale_handles_negative_rewards(self):
        u, lo, hi = to_unit(np.array([[-0.2, 0.5], [1.0, 0.0]]))
        self.assertAlmostEqual(u.min(), 0.0)
        self.assertAlmostEqual(u.max(), 1.0)
        res = replay(self.R - 0.3, self.X, algos=("thompson",), n_orders=3, cell_cols=CELLS, horizon=60)
        self.assertEqual(res["thompson"]["vs_oracle"].shape, (3, 60))


class OPECase(unittest.TestCase):
    def test_estimators_close_to_truth_and_propensities_stored(self):
        R, X, _ = synthetic(300, seed=2)
        cells = cell_codes(X, CELLS)
        K = R.shape[1]
        P = propensities_epsilon(np.full(len(R), 0), K, 0.4)
        log = simulate_log(R, X, cells, P, 8000, seed=3)
        self.assertTrue((log["propensity"] > 0).all())
        self.assertTrue(np.allclose(log["propensity"], P[0, log["arm_idx"]]))
        nc = int(cells.max()) + 1
        for name, tp in (("greedy", best_arm_per_cell(R, X, cells)), ("uniform", np.full((nc, K), 1 / K))):
            truth = true_value(R, X, cells, tp)
            est = ope_estimates(log, tp, nc)
            self.assertLess(abs(est["snips"] - truth), 0.05, name)
            self.assertLess(abs(est["dr"] - truth), 0.05, name)
            self.assertLess(abs(est["ips"] - truth), 0.12, name)

    def test_check_ope_table(self):
        R, X, _ = synthetic(200, seed=4)
        out = check_ope(R, X, cell_cols=CELLS, n_log=6000, seed=5)
        self.assertEqual(set(out["estimator"]), {"ips", "snips", "dr", "dm"})
        self.assertLess(out.loc[out["estimator"].isin(["snips", "dr"]), "error"].abs().max(), 0.06)

    def test_zero_propensity_rejected(self):
        R, X, _ = synthetic(60, seed=0)
        cells = cell_codes(X, CELLS)
        log = simulate_log(R, X, cells, propensities_epsilon(np.zeros(len(R), int), R.shape[1], 0.5), 50)
        log.loc[0, "propensity"] = 0.0
        with self.assertRaises(ValueError):
            ope_estimates(log, np.full((int(cells.max()) + 1, R.shape[1]), 1 / R.shape[1]))


class FeedbackCase(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "feedback.jsonl"
            self.assertEqual(len(load_feedback(p)), 0)
            log_feedback(p, {"source_id": "s1", "arm": "gen-a:plain", "propensity": 0.25, "thumbs": "up"})
            log_feedback(p, {"source_id": "s2", "arm": "deterministic", "propensity": None, "thumbs": "down"})
            log_feedback(p, {"source_id": "s3", "arm": "gen-a:chunked", "propensity": 0.5, "reward": 0.7})
            df = load_feedback(p)
            self.assertEqual(list(df["source_id"]), ["s1", "s2", "s3"])
            self.assertEqual(list(df["reward"]), [1.0, 0.0, 0.7])
            self.assertTrue(df["timestamp"].notna().all())
            self.assertEqual(df.loc[0, "propensity"], 0.25)
            with self.assertRaises(ValueError):
                log_feedback(p, {"source_id": "s4", "arm": "x", "propensity": 0.0})


if __name__ == "__main__":
    unittest.main()
