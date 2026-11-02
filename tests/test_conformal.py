"""Run: python -m unittest tests.test_conformal -v   (offline, fast)"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conformal import (NEG_INF, crc_threshold, guarantee_curve, ltt_threshold, risk_score,  # noqa: E402
                       split_by_source, synthetic)

RAND = np.random.default_rng(0)


def row(det_flags=(), critic="SAFE", program="MATCH") -> dict:
    flags = [{"code": f"F{i}", "severity": sev, "detail": ""} for i, sev in enumerate(det_flags)]
    c = None if critic is None else ({"_error": "x"} if critic == "ERR" else {"overall": critic})
    return {"output_id": "o", "deterministic": {"decision": "PASS", "flags": flags}, "critic": c,
            "program": None if program is None else {"status": program}}


class RiskScoreCase(unittest.TestCase):
    def test_risk_score_monotone_in_layers(self):
        ladder = [row(),                                   # clean
                  row(["REVIEW"]),                         # review flag only
                  row(critic="UNSURE"),                    # unsure critic
                  row(program="MISMATCH"),                 # program mismatch
                  row(critic="UNSAFE"),                    # critic unsafe
                  row(["REJECT"])]                         # det reject
        s = [risk_score(r) for r in ladder]
        self.assertEqual(s, sorted(s))
        self.assertEqual(len(set(s)), len(s))

    def test_unsure_variants_tie_and_extra_evidence_never_lowers(self):
        base = risk_score(row())
        self.assertEqual(risk_score(row(critic=None)), risk_score(row(critic="ERR")))
        self.assertEqual(risk_score(row(critic="UNSURE")), risk_score(row(program="UNCHECKABLE")))
        self.assertGreater(risk_score(row(["REVIEW", "REVIEW"])), risk_score(row(["REVIEW"])))
        # worst of a lower layer plus many flags stays below the next layer's base
        self.assertLess(risk_score(row(["REVIEW"] * 20, program="MISMATCH")), risk_score(row(critic="UNSAFE")))
        for r in (row(["REJECT"], "UNSAFE", "MISMATCH"), row(["REVIEW"], "UNSURE")):
            self.assertGreaterEqual(risk_score(r), base)


class ThresholdCase(unittest.TestCase):
    def test_crc_empirical_risk_below_alpha_synthetic(self):
        df, rows = synthetic(n_sources=300, seed=1)
        c = guarantee_curve(df, rows, alphas=(0.1,), n_splits=100, method="crc", seed=7).iloc[0]
        self.assertGreaterEqual(c["frac_splits_unsafe_pass_below_alpha"], 0.85)
        self.assertLessEqual(c["realized_unsafe_pass_mean"], 0.1 + 0.02)

    def test_crc_passes_nothing_when_impossible(self):
        scores = np.tile([1.0, 2.0, 3.0], 20)
        self.assertEqual(crc_threshold(scores, np.ones(60), alpha=0.05), NEG_INF)
        self.assertEqual(crc_threshold(np.array([]), np.array([]), alpha=0.1), NEG_INF)

    def test_crc_formula_and_groups(self):
        scores = np.arange(10, dtype=float)
        loss = np.zeros(10)
        loss[5:] = 1  # unsafe from score 5 up: risk(lam) = 0 for lam <= 4
        # n=10: bound at lam=4 is 10/11*0 + 1/11 = .0909 <= .1; at lam=5 it is 10/11*.1 + 1/11 = .1818
        self.assertEqual(crc_threshold(scores, loss, alpha=0.1), 4.0)
        groups = np.repeat(np.arange(5), 2)  # n = 5 groups -> B/(n+1) = .1667 > .1
        self.assertEqual(crc_threshold(scores, loss, alpha=0.1, groups=groups), NEG_INF)
        self.assertEqual(crc_threshold(scores, loss, alpha=0.2, groups=groups), 4.0)

    def test_ltt_fixed_sequence_stops(self):
        # scores 0..9, 60 items each (0.95**45 < 0.1, so a clean level certifies after 45 items); levels 0-4 are clean, level 5 is 50% unsafe, 6-9 clean again.
        scores = np.repeat(np.arange(10, dtype=float), 60)
        unsafe = np.zeros_like(scores, dtype=int)
        unsafe[(scores == 5)] = np.tile([0, 1], 30)
        lam = ltt_threshold(scores, unsafe, alpha=0.05, delta=0.1)
        self.assertEqual(lam, 4.0)  # risk jumps above alpha at 5; later clean levels are never reached
        self.assertEqual(ltt_threshold(scores[scores >= 5], unsafe[scores >= 5], alpha=0.05), NEG_INF)
        # group version is conservative: never more lenient than the item version
        g = np.repeat(np.arange(len(scores) // 5), 5)
        self.assertLessEqual(ltt_threshold(scores, unsafe, 0.05, 0.1, groups=g), lam)

    def test_ltt_conditional_risk_controlled_synthetic(self):
        df, rows = synthetic(n_sources=300, seed=2)
        c = guarantee_curve(df, rows, alphas=(0.2,), n_splits=40, method="ltt", seed=3).iloc[0]
        self.assertGreaterEqual(c["frac_splits_risk_below_alpha"], 0.85)

    def test_ltt_valid_without_monotone_scores(self):
        """Conditional risk P(unsafe | score <= lam) is NOT monotone here (dips, then rises); FWER must still be <= delta."""
        levels = np.arange(6)
        p_level = np.array([0.01, 0.02, 0.0, 0.25, 0.02, 0.6])      # unsafe rate by score level
        w = np.full(6, 1 / 6)
        cum_risk = np.cumsum(w * p_level) / np.cumsum(w)            # true P(unsafe | score <= lam)
        self.assertFalse(np.all(np.diff(cum_risk) >= 0))
        alpha, delta, errors, rng = 0.06, 0.1, 0, np.random.default_rng(21)
        for _ in range(400):
            sc = rng.choice(levels, 400)
            un = (rng.random(400) < p_level[sc]).astype(int)
            lam = ltt_threshold(sc.astype(float), un, alpha, delta)
            if lam != NEG_INF and cum_risk[int(lam)] > alpha:
                errors += 1
        self.assertLessEqual(errors / 400, delta + 0.03)

    def test_split_by_source_disjoint(self):
        df, _ = synthetic(n_sources=30)
        cal, test = split_by_source(df, 0.5, seed=1)
        self.assertFalse(set(cal["source_id"]) & set(test["source_id"]))
        self.assertEqual(len(cal) + len(test), len(df))


class CurveCase(unittest.TestCase):
    def test_guarantee_curve_columns_and_monotone(self):
        df, rows = synthetic(n_sources=80, seed=4)
        c = guarantee_curve(df, rows, alphas=(0.05, 0.1, 0.2), n_splits=15, method="crc")
        for col in ("method", "alpha", "lambda_mean", "review_rate_mean", "review_rate_lo", "review_rate_hi",
                    "realized_risk_mean", "realized_risk_lo", "realized_risk_hi", "frac_splits_risk_below_alpha"):
            self.assertIn(col, c.columns)
        self.assertEqual(list(c["alpha"]), [0.05, 0.1, 0.2])
        self.assertTrue((np.diff(c["review_rate_mean"]) < 0).all())

    def test_by_condition_breakdown(self):
        df, rows = synthetic(n_sources=60, seed=5)
        c = guarantee_curve(df, rows, alphas=(0.1,), n_splits=5, by=["transformation"])
        self.assertEqual(set(c["transformation"]), {"ALL", "naive", "chunked", "rename"})
        r = c.set_index("transformation")["review_rate_mean"]
        self.assertGreater(r["naive"], r["rename"])  # naive rewrites carry more evidence of harm


if __name__ == "__main__":
    unittest.main()
