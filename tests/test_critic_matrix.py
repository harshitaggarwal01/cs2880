"""critic_matrix.py on synthetic labels with planted self-preference (no files, no network)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import critic_matrix as cm  # noqa: E402


class CriticMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.labels, cls.fams, cls.costs = cm.synthetic(n_sources=150, seed=1, self_pref=2.0)
        cls.matrix, cls.sp, cls.ens, cls.par = cm.analyse(cls.rows, cls.labels, cls.fams, cls.costs, "critQ", "critA",
                                                          b=60, n_boot=60)

    def test_self_preference_recovered(self):
        r = self.sp[self.sp["term"] == "same_family"].iloc[0]
        self.assertGreater(r["coef"], 1.0)
        self.assertLess(r["coef"], 3.0)
        self.assertGreater(r["or_lo"], 1.0)

    def test_no_planted_effect_ci_covers_zero(self):
        rows, labels, fams, costs = cm.synthetic(n_sources=150, seed=2, self_pref=0.0)
        df = cm.wide(rows, labels, fams["gen_family"], fams["critic_family"], costs)
        r = cm.self_preference(df, n_boot=60).set_index("term").loc["same_family"]
        self.assertLess(r["or_lo"], 1.0)
        self.assertGreater(r["or_hi"], 1.0)

    def test_not_identified_with_one_family(self):
        rows = {"critA": self.rows["critA"]}
        fams = {"gen_family": {"genA": "anthropic", "genQ": "anthropic"}, "critic_family": {"critA": "anthropic"}}
        df = cm.wide(rows, self.labels, fams["gen_family"], fams["critic_family"], self.costs)
        r = cm.self_preference(df).iloc[0]
        self.assertEqual(r["method"], "none")
        self.assertIn("not identified", r["note"])

    def test_critic_table_shapes_and_ranges(self):
        t = self.matrix[self.matrix["kind"] == "critic"]
        self.assertEqual(set(t["critic"]), {"critA", "critA2", "critQ"})
        self.assertEqual(set(t["basis"]), {"critic_verdict", "full_verifier"})
        for c in ("recall_unsafe", "precision", "review_rate"):
            self.assertTrue(t[c].between(0, 1).all(), c)
        self.assertTrue((t["recall_lo"] <= t["recall_unsafe"] + 1e-9).all())
        cost = t.set_index(["critic", "basis"])["usd_per_item"]
        self.assertAlmostEqual(cost[("critQ", "critic_verdict")], 0.0005)
        self.assertTrue(t["risk_auc"].between(0.5, 1).all())

    def test_grid_same_family_more_lenient(self):
        g = self.matrix[self.matrix["kind"] == "grid"]
        same = g[g["same_family"] == True]["false_safe_rate"].mean()  # noqa: E712
        cross = g[g["same_family"] == False]["false_safe_rate"].mean()  # noqa: E712
        self.assertGreater(same, cross)
        self.assertEqual(len(g), 2 * 3)

    def test_ensembles(self):
        e = self.ens[self.ens["basis"] == "critic_verdict"].set_index("critic")
        self.assertEqual(set(e.index), {"majority", "any_unsafe", "cascade:critQ>critA"})
        single = self.matrix[(self.matrix["kind"] == "critic") & (self.matrix["basis"] == "critic_verdict")]
        self.assertGreaterEqual(e.loc["any_unsafe", "recall_unsafe"], single["recall_unsafe"].max() - 1e-9)
        # cascade: never costs more than cheap + expensive, never less than cheap alone
        self.assertLessEqual(e.loc["cascade:critQ>critA", "usd_per_item"], 0.0205 + 1e-9)
        self.assertGreaterEqual(e.loc["cascade:critQ>critA", "usd_per_item"], 0.0005 - 1e-12)

    def test_cascade_semantics(self):
        df = cm.wide(self.rows, self.labels, self.fams["gen_family"], self.fams["critic_family"], self.costs)
        d = cm.ensemble_verdicts(df, "critQ", "critA")
        col = "safe_cascade:critQ>critA"
        cheap_safe = d["safe_critQ"] == 1
        self.assertTrue((d.loc[cheap_safe, col] == 1).all())
        self.assertTrue((d.loc[~cheap_safe, col] == d.loc[~cheap_safe, "safe_critA"]).all())
        usd = d["usd_cascade:critQ>critA"]
        self.assertTrue(np.allclose(usd[cheap_safe], 0.0005))
        self.assertTrue(np.allclose(usd[~cheap_safe], 0.0205))
        maj = d["safe_majority"].to_numpy()
        votes = d[["safe_critA", "safe_critA2", "safe_critQ"]].sum(axis=1).to_numpy()
        self.assertTrue(((votes >= 2) == (maj == 1)).all())

    def test_pareto_has_every_option_and_global_frontier(self):
        self.assertEqual(set(self.par["critic_option"]),
                         {"critA", "critA2", "critQ", "majority", "any_unsafe", "cascade:critQ>critA"})
        self.assertTrue(self.par["is_pareto_global"].any())
        self.assertTrue((self.par["is_pareto_global"] <= self.par["is_pareto"]).all())

    def test_says_safe(self):
        self.assertEqual(cm.says_safe({"overall": "SAFE"}), 1)
        for c in (None, {"overall": "UNSURE"}, {"overall": "UNSAFE"}, {"_error": "x", "overall": "SAFE"}):
            self.assertEqual(cm.says_safe(c), 0)


if __name__ == "__main__":
    unittest.main()
