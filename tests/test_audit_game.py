"""Run: python -m unittest tests.test_audit_game -v   (offline; synthetic data only)"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_game import (Game, build_game, compare, evaluate_allocation, proportional_allocation,  # noqa: E402
                        solve_robust, solve_sse, synthetic_game, uniform_allocation)


def two_target(a, mode="targets"):
    a = np.array(a, float)
    return Game(["A", "B"], a, a * 0.8, np.minimum(a * 1.2, 1e9), np.ones(2), budget_mode=mode)


class SSECase(unittest.TestCase):
    def test_closed_form_equalising_equilibrium(self):
        # zero-sum, detect = 1: loss_t = a_t (1 - c_t); equalise at L = (T - B) / sum(1/a)
        g = two_target([4.0, 2.0])
        r = solve_sse(g, 1.0)
        L = (2 - 1.0) / (1 / 4 + 1 / 2)
        np.testing.assert_allclose(r["c"], [1 - L / 4, 1 - L / 2], atol=1e-7)
        self.assertAlmostEqual(r["defender_utility"], -L, places=7)

    def test_closed_form_corner_equilibrium(self):
        # budget too small to reach target B: all coverage goes to A until A's loss falls to B's (here never)
        g = two_target([10.0, 1.0])
        r = solve_sse(g, 0.5)
        np.testing.assert_allclose(r["c"], [0.5, 0.0], atol=1e-7)
        self.assertAlmostEqual(r["defender_utility"], -5.0, places=7)

    def test_budget_extremes_feasible(self):
        g = synthetic_game(seed=1)
        none = solve_sse(g, 0.0)
        np.testing.assert_allclose(none["c"], 0, atol=1e-9)
        self.assertAlmostEqual(none["defender_utility"], -(g.harm * g.loss(np.zeros(g.n))).max(), places=6)
        full = solve_sse(g, g.full_budget)
        self.assertAlmostEqual(full["defender_utility"], 0.0, places=6)
        self.assertLessEqual((g.weight * full["c"]).sum(), g.full_budget + 1e-7)

    def test_sse_beats_uniform_and_proportional(self):
        for seed in range(4):
            g = synthetic_game(seed=seed)
            for frac in (0.05, 0.1, 0.3):
                B = frac * g.full_budget
                sse = evaluate_allocation(g, solve_sse(g, B)["c"])["defender_loss"]
                for c in (uniform_allocation(g, B), proportional_allocation(g, B)):
                    self.assertLessEqual(sse, evaluate_allocation(g, c)["defender_loss"] + 1e-7)
                    self.assertLessEqual((g.weight * c).sum(), B + 1e-7)

    def test_general_sum_sse_is_best_response_consistent(self):
        g = synthetic_game(seed=3)
        g.gain = np.random.default_rng(0).uniform(0.5, 2.0, g.n)
        B = 0.15 * g.full_budget
        r = solve_sse(g, B)
        ua = g.gain * g.loss(r["c"])
        self.assertGreaterEqual(ua[r["target"]], ua.max() - 1e-6)       # attacker's choice is a best response


class RobustCase(unittest.TestCase):
    def test_robust_never_worse_in_worst_case(self):
        for seed in range(4):
            g = synthetic_game(seed=seed)
            for frac in (0.0, 0.1, 0.3, 1.0):
                B = frac * g.full_budget
                rob = evaluate_allocation(g, solve_robust(g, B)["c"])["worst_case_loss"]
                nom = evaluate_allocation(g, solve_sse(g, B)["c"])["worst_case_loss"]
                self.assertLessEqual(rob, nom + 1e-7)
                self.assertLessEqual((g.weight * solve_robust(g, B)["c"]).sum(), B + 1e-7)

    def test_no_uncertainty_matches_nominal_zero_sum(self):
        g = synthetic_game(seed=2)
        g.lo, g.hi = g.p.copy(), g.p.copy()
        B = 0.2 * g.full_budget
        self.assertAlmostEqual(solve_robust(g, B)["worst_case_loss"], -solve_sse(g, B)["defender_utility"], places=5)


class BuilderCase(unittest.TestCase):
    def test_build_from_ppi_like_table_and_compare(self):
        df = pd.DataFrame({"transformation": ["plain", "chunked"], "generator": ["a", "a"], "ppipp": [0.1, 0.3],
                           "ppipp_lo": [0.05, 0.2], "ppipp_hi": [0.15, 0.4], "n_all": [100, 200]})
        g = build_game(df)
        self.assertEqual(g.names, ["plain / a", "chunked / a"])
        out = compare(g, [0.0, 30.0, 300.0])
        self.assertEqual(set(out["method"]), {"sse", "robust", "uniform", "proportional"})
        self.assertTrue((out.loc[out["budget"] == 300.0, "unsafe_per_1000"] < 1e-6).all())
        g2 = build_game(pd.DataFrame({"group": ["x", "y"], "rate": [0.2, 0.1], "lo": [0.1, 0.0], "hi": [0.3, 0.2],
                                      "n": [50, 50]}))
        self.assertEqual(g2.names, ["x", "y"])


if __name__ == "__main__":
    unittest.main()
