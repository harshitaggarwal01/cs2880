"""Run: python -m unittest tests.test_ppi -v   (offline; planted data only)

The synthetic data is CONSTRUCTED for software testing. Nothing here is a measured model failure rate.
"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ppi import (FULL, classical_mean, estimate_rates, label_budget_curve, load_run, ppi_lambda,  # noqa: E402
                 ppi_mean, ppi_pp_mean, predictor_from_verify, synthetic)

BOOT = 200   # small bootstraps keep the whole file well under a minute


def _subset(df, frac, rng):
    """Row mask for a random `frac` of sources."""
    units = df["source_id"].unique()
    take = set(rng.choice(units, int(round(frac * len(units))), replace=False))
    return df["source_id"].isin(take).to_numpy()


def _runs(df, frac, n_rep, seed=0, n_boot=BOOT):
    """Per repetition: (classical, ppi, ppipp) tuples from a fresh random labelled subset."""
    rng = np.random.default_rng(seed)
    y, f, cl = df["UNSAFE"].to_numpy(float), df["f"].to_numpy(float), df["source_id"].to_numpy()
    out = []
    for r in range(n_rep):
        m = _subset(df, frac, rng)
        out.append((classical_mean(y[m], cl[m], n_boot=n_boot, seed=r),
                    ppi_mean(y[m], f[m], f, cluster_lab=cl[m], cluster_all=cl, n_boot=n_boot, seed=r),
                    ppi_pp_mean(y[m], f[m], f, cluster_lab=cl[m], cluster_all=cl, n_boot=n_boot, seed=r)))
    return out


class Estimators(unittest.TestCase):
    def test_ppi_unbiased_under_biased_predictor(self):
        df = synthetic(n_sources=200, predictor_bias=0.15, seed=1)
        true = df["UNSAFE"].mean()
        self.assertGreater(abs(df["f"].mean() - true), 0.1, "the planted predictor must be visibly biased")
        runs = _runs(df, 0.5, 50, n_boot=20)
        ppi_avg = np.mean([p[0] for _, p, _ in runs])
        self.assertLess(abs(ppi_avg - true), 0.03)
        self.assertLess(np.mean([abs(p[0] - true) for _, p, _ in runs]), 0.05)

    def test_ppi_narrower_when_predictor_accurate(self):
        df = synthetic(n_sources=150, predictor_acc=0.95, predictor_bias=0.03, seed=2)
        runs = _runs(df, 0.3, 30)
        w_cls = np.mean([c[2] - c[1] for c, _, _ in runs])
        w_ppi = np.mean([p[2] - p[1] for _, p, _ in runs])
        w_pp = np.mean([q[2] - q[1] for _, _, q in runs])
        self.assertLess(w_ppi, w_cls)
        self.assertLess(w_pp, w_cls)

    def test_ppipp_lambda_bounded(self):
        for acc, bias, seed in ((0.95, 0.03, 3), (0.85, 0.1, 4), (0.7, 0.2, 5), (0.5, 0.0, 6)):
            df = synthetic(predictor_acc=acc, predictor_bias=bias, seed=seed)
            m = _subset(df, 0.3, np.random.default_rng(seed))
            lam = ppi_lambda(df.loc[m, "UNSAFE"], df.loc[m, "f"], len(df))
            self.assertGreaterEqual(lam, 0.0)
            self.assertLessEqual(lam, 1.0)
        # useless predictor: lam ~ 0 and PPI++ collapses to the classical estimate
        df = synthetic(predictor_acc=0.5, predictor_bias=0.0, seed=7)
        m = _subset(df, 0.3, np.random.default_rng(7))
        y, f, cl = df["UNSAFE"].to_numpy(float), df["f"].to_numpy(float), df["source_id"].to_numpy()
        est, lo, hi, lam = ppi_pp_mean(y[m], f[m], f, cluster_lab=cl[m], cluster_all=cl, n_boot=BOOT)
        c_est, c_lo, c_hi = classical_mean(y[m], cl[m], n_boot=BOOT)
        self.assertLess(lam, 0.05)
        self.assertAlmostEqual(est, c_est, delta=0.01)
        self.assertAlmostEqual(hi - lo, c_hi - c_lo, delta=0.02)
        # explicit lam = 0 is exactly classical, lam = 1 is exactly PPI
        self.assertAlmostEqual(ppi_pp_mean(y[m], f[m], f, lam=0.0, n_boot=10)[0], y[m].mean())
        self.assertAlmostEqual(ppi_pp_mean(y[m], f[m], f, lam=1.0, n_boot=10)[0],
                               ppi_mean(y[m], f[m], f, n_boot=10)[0])

    def test_coverage_near_nominal(self):
        df = synthetic(n_sources=150, predictor_acc=0.9, predictor_bias=0.08, seed=8)
        curve = label_budget_curve(df, fracs=(0.3,), n_rep=200, n_boot=BOOT, seed=8)
        self.assertEqual(len(curve), 1)
        for name in ("classical", "ppi", "ppipp"):
            self.assertGreaterEqual(curve[f"cov_{name}"].iloc[0], 0.88, name)

    def test_classical_normal_vs_cluster(self):
        y = np.array([0, 1, 1, 0, 1, 0, 0, 0, 1, 1], float)
        est, lo, hi = classical_mean(y)
        self.assertAlmostEqual(est, 0.5)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        est2, lo2, hi2 = classical_mean(y, cluster=np.arange(10) // 2, n_boot=100)
        self.assertAlmostEqual(est2, 0.5)
        self.assertTrue(lo2 <= est2 <= hi2)
        self.assertTrue(np.isnan(classical_mean(np.array([1.0]))[1]))


class Tables(unittest.TestCase):
    def test_estimate_rates_columns(self):
        df = synthetic(n_sources=60, seed=9)
        m = _subset(df, 0.5, np.random.default_rng(9))
        t = estimate_rates(df, m, n_boot=50)
        self.assertEqual(t.iloc[0]["transformation"], "all")
        self.assertEqual(int(t.iloc[0]["n_all"]), len(df))
        self.assertEqual(int(t.iloc[0]["n_lab"]), int(m.sum()))
        self.assertEqual(int(t["n_all"].iloc[1:].sum()), len(df))
        for col in ("classical", "ppi", "ppipp", "lam", "ppi_width", "ppipp_lo"):
            self.assertIn(col, t)
        self.assertTrue(((t["lam"] >= 0) & (t["lam"] <= 1)).all())

    def test_predictor_from_verify_mapping(self):
        rows = [{"output_id": "a", "decision": "PASS", "critic": {"overall": "SAFE"}},
                {"output_id": "b", "decision": "REVIEW", "critic": {"overall": "UNSURE"}},
                {"output_id": "c", "decision": "REJECT", "critic": {"overall": "UNSAFE"}},
                {"output_id": "d", "decision": "PASS", "critic": None},
                {"output_id": "e", "decision": "REVIEW", "critic": {"_error": "max_tokens"}},
                {"output_id": "f", "decision": "PASS", "critic": {"overall": "SAFE", "_error": None}}]
        self.assertEqual(predictor_from_verify(rows, "decision"), {"a": 0, "b": 1, "c": 1, "d": 0, "e": 1, "f": 0})
        self.assertEqual(predictor_from_verify(rows, "critic"), {"a": 0, "b": 1, "c": 1, "d": 1, "e": 1, "f": 0})
        with self.assertRaises(ValueError):
            predictor_from_verify(rows, "oracle")

    def test_synthetic_shape_and_attrs(self):
        df = synthetic(n_sources=40, per_source=5, predictor_acc=0.85, predictor_bias=0.1, seed=10)
        self.assertEqual(len(df), 200)
        self.assertEqual(df["source_id"].nunique(), 40)
        self.assertEqual(set(df.columns), {"output_id", "source_id", "transformation", "generator", "UNSAFE", "f"})
        self.assertTrue(df["output_id"].is_unique)
        self.assertTrue(set(df["f"].unique()) <= {0, 1})
        self.assertAlmostEqual(df.attrs["accuracy"], 0.85, delta=0.06)
        self.assertAlmostEqual(df.attrs["bias"], 0.1, delta=0.06)

    def test_load_run_joins_labels_and_predictor(self):
        """A hand-built run: 3 sources x 2 conditions, verify rows for all, adjudicated labels for 4 of 6."""
        good = {"math_fidelity": "PASS", "target_preserved": "PASS", "solvability_changed": "NO", "ambiguity": "NO",
                "leakage_level": 0, "presentation": 3, "failure_codes": "", "abstention_appropriate": "NO"}
        bad = {**good, "leakage_level": 2, "failure_codes": "LEAK_ANSWER"}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "outputs" / "fake-run"
            ann = Path(tmp) / "ann"
            run.mkdir(parents=True), ann.mkdir()
            gens, ver, key, labels = [], [], [], []
            for s in ("s1", "s2", "s3"):
                for tf in ("plain", "chunked"):
                    oid = f"fake|gen|{tf}|{s}"
                    gens.append({"output_id": oid, "source_id": s, "transformation": tf, "generator": "gen",
                                 "adapted_problem": "x"})
                    unsafe = (s, tf) in {("s1", "plain"), ("s2", "chunked")}
                    ver.append({"output_id": oid, "decision": "REJECT" if unsafe or s == "s3" else "PASS",
                                "critic": {"overall": "UNSAFE" if unsafe else "SAFE"}})
                    if s != "s3":   # s3 is unlabelled
                        aid = f"a{s}{tf}"
                        key.append({"annotation_id": aid, "output_id": oid, "source_id": s, "generator": "gen",
                                    "transformation": tf, "partition": "main", "is_repair": False, "repair_of": "",
                                    "double": False})
                        labels.append({"annotation_id": aid, "annotator": "ADJ", **(bad if unsafe else good)})
                        labels.append({"annotation_id": aid, "annotator": "A", **good})   # pre-adjudication row
            (run / "generations.jsonl").write_text("\n".join(json.dumps(g) for g in gens) + "\n")
            (run / f"generations.{FULL}.jsonl").write_text("\n".join(json.dumps(v) for v in ver) + "\n")
            for name, rows in (("KEY_DO_NOT_OPEN.csv", key), ("adjudicated.csv", labels)):
                with open(ann / name, "w", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                    w.writeheader()
                    w.writerows(rows)
            df, mask = load_run(run, ann / "adjudicated.csv", ann / "KEY_DO_NOT_OPEN.csv")
            self.assertEqual(len(df), 6)
            self.assertEqual(int(mask.sum()), 4)
            self.assertEqual(df.loc[mask, "UNSAFE"].sum(), 2)
            self.assertEqual(df["f"].sum(), 4)                      # 2 unsafe + 2 rejected s3 rows
            self.assertTrue(df.loc[~mask, "UNSAFE"].isna().all())
            self.assertEqual(set(df["source_id"]), {"s1", "s2", "s3"})
            df2, _ = load_run(run, ann / "adjudicated.csv", ann / "KEY_DO_NOT_OPEN.csv", predictor="critic")
            self.assertEqual(df2["f"].sum(), 2)
            t = estimate_rates(df, mask, n_boot=20)
            self.assertAlmostEqual(t.iloc[0]["classical"], 0.5)
            self.assertAlmostEqual(t.iloc[0]["ppi"], 4 / 6 + (2 - 2) / 4)   # mean(f_all) + mean(y - f) on labelled


if __name__ == "__main__":
    unittest.main()
