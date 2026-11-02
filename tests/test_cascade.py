"""Run: python -m unittest tests.test_cascade -v   (from the repo root). Synthetic data only."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cascade  # noqa: E402
from evaluate import verifier_metrics  # noqa: E402

COSTS = {"critic_usd": 0.01, "extract_usd": 0.008, "minutes_per_review": 1.5}


def named(name: str) -> dict:
    return next(p for p in cascade.enumerate_policies() if cascade.policy_name(p) == name)


class Cascade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vrows, cls.labels = cascade.synthetic(n_sources=120, per_source=6, seed=0)
        cls.df = cascade.frame(cls.vrows, cls.labels)

    def test_synthetic_structure(self):
        d = self.df
        self.assertEqual(len(d), 720)
        det_rej = d["_row"].map(lambda r: r["deterministic"]["decision"] == "REJECT")
        self.assertGreater((1 - d["SAFE"])[det_rej].mean(), 0.75)  # REJECT => mostly unsafe
        naive = d["transformation"] == "naive"
        self.assertGreater((1 - d["SAFE"])[naive].mean(), (1 - d["SAFE"])[~naive].mean())

    def test_enumerate_policies_distinct(self):
        policies = cascade.enumerate_policies()
        names = [cascade.policy_name(p) for p in policies]
        self.assertEqual(len(names), len(set(names)))
        for n in ("det_only_ship_rest", "det_only_human_rest", "full_verifier_human_review", "human_everything"):
            self.assertIn(n, names)
        # the synthetic set plus one row per (det, critic, program) outcome, so every behavioural difference shows
        rows = self.df.copy()
        probes = cascade.probe_rows()
        rows = pd.concat([rows, pd.DataFrame({"output_id": [r["output_id"] for r in probes], "SAFE": 1,
                                              "source_id": "probe", "_row": probes, **{k: v for k, v in COSTS.items()}})],
                         ignore_index=True)
        vectors = [tuple(cascade._run(rows, p)[0]) for p in policies]
        self.assertEqual(len(vectors), len(set(vectors)))

    def test_pareto_no_dominated(self):
        t = cascade.pareto(self.df)
        self.assertTrue(t["is_pareto"].any())
        self.assertFalse(t["is_pareto"].all())
        m = t[["unsafe_shipped_per100", "usd_per100", "minutes_per100"]].to_numpy()
        for i in np.flatnonzero(t["is_pareto"]):
            dominated = (m <= m[i]).all(axis=1) & (m < m[i]).any(axis=1)
            self.assertFalse(dominated.any(), t.loc[i, "policy_name"])

    def test_cascade_det_only_matches_verifier_metrics(self):
        t = cascade.pareto(self.df, [named("full_verifier_human_review")])
        d = self.df.copy()
        d["FLAG_ANY"] = d["_row"].map(lambda r: int(r["decision"] != "PASS"))
        m = verifier_metrics(d.drop(columns="_row"), "FLAG_ANY", 5)
        self.assertAlmostEqual(t.loc[0, "recall_unsafe"], m["recall_unsafe"], places=7)

    def test_human_everything_zero_unsafe(self):
        p = named("human_everything")
        o = cascade.objective(self.df, p, lam=10, mu=1)
        self.assertEqual(o["unsafe_shipped"], 0)
        self.assertEqual(o["safe_rejected"], 0)
        self.assertAlmostEqual(o["human_items"], 100)
        self.assertAlmostEqual(o["minutes"], 150)
        self.assertEqual(o["usd"], 0)
        t = cascade.pareto(self.df, [p])
        self.assertEqual(t.loc[0, "recall_unsafe"], 1.0)

    def test_simulate_costs_accumulate(self):
        review = {"deterministic": {"decision": "REVIEW", "flags": [{"code": "X", "severity": "REVIEW"}]},
                  "critic": {"overall": "UNSURE"}, "program": {"status": "MATCH"}}
        safe = {"deterministic": {"decision": "PASS", "flags": []}, "critic": {"overall": "SAFE"},
                "program": {"status": "MATCH"}}
        rej = {"deterministic": {"decision": "REJECT", "flags": [{"code": "X", "severity": "REJECT"}]},
               "critic": None, "program": None}
        p = cascade._policy(s1_stop_reject=True, s2_stop_unsafe=True, s2_stop_safe=True, s2_unsure_to_human=True)
        self.assertEqual(cascade.simulate(rej, p, COSTS), ("reject", 0.0, 0.0))  # stopped at S1: free
        a, usd, mins = cascade.simulate(safe, p, COSTS)  # S2 only
        self.assertEqual(a, "ship")
        self.assertAlmostEqual(usd, 0.018)
        self.assertEqual(mins, 0.0)
        a, usd, mins = cascade.simulate(review, p, COSTS)  # S2 then S3
        self.assertEqual(a, "human")
        self.assertAlmostEqual(usd, 0.018)
        self.assertAlmostEqual(mins, 1.5)
        a, usd, mins = cascade.simulate(review, p, {**COSTS, "critic_usd": 0.05, "minutes_per_review": 3})
        self.assertAlmostEqual(usd, 0.058)
        self.assertAlmostEqual(mins, 3)

    def test_stage_semantics(self):
        row = {"deterministic": {"decision": "PASS", "flags": []}, "critic": {"overall": "SAFE"},
               "program": {"status": "MISMATCH"}}
        p = cascade._policy(s2_stop_unsafe=True, s2_stop_safe=True, s2_unsure_to_human=True)
        self.assertEqual(cascade.simulate(row, p, COSTS)[0], "reject")  # MISMATCH beats critic SAFE
        p2 = cascade._policy(s2_stop_safe=True, s2_unsure_to_human=True)
        self.assertEqual(cascade.simulate(row, p2, COSTS)[0], "human")  # not safe_sig: goes to the human
        p3 = cascade._policy(s1_stop_pass=True)
        flagged = {**row, "deterministic": {"decision": "PASS", "flags": [{"code": "INFO", "severity": "INFO"}]}}
        self.assertAlmostEqual(cascade.simulate(flagged, p3, COSTS)[1], 0.018)  # flags: S1 does not stop it

    def test_stage_costs_and_frame(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            led = Path(d) / "ledger.csv"
            pd.DataFrame([{"output_id": "S000.haiku55.plain", "stage": "critic", "usd": 0.02},
                          {"output_id": "S000.haiku55.plain", "stage": "extract", "usd": 0.005},
                          {"output_id": "S000.haiku55.plain", "stage": "gen", "usd": 0.001}]).to_csv(led, index=False)
            sc = cascade.stage_costs(led)
        self.assertAlmostEqual(sc["S000.haiku55.plain"]["critic"], 0.02)
        df = cascade.frame(self.vrows, self.labels, sc)
        r = df[df["output_id"] == "S000.haiku55.plain"].iloc[0]
        self.assertAlmostEqual(r["critic_usd"], 0.02)
        self.assertAlmostEqual(r["extract_usd"], 0.005)
        other = df[df["output_id"] == "S000.sonnet55.plain"].iloc[0]
        self.assertAlmostEqual(other["critic_usd"], 0.01)  # not in the ledger: default

    def test_calibrate_and_test(self):
        t = cascade.calibrate_and_test(self.df, lam=10, mu=1, seed=1, n_splits=20)
        self.assertEqual(t.loc[0, "policy_name"], "(all splits)")
        self.assertAlmostEqual(t["freq"].iloc[1:].sum(), 1.0)
        self.assertTrue((t["objective_lo"] <= t["objective_hi"]).all())
        t2 = cascade.calibrate_and_test(self.df, lam=10, mu=1, seed=1, n_splits=20)
        pd.testing.assert_frame_equal(t, t2)


if __name__ == "__main__":
    unittest.main()
