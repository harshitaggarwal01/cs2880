"""Run: python -m unittest tests.test_run_safety -v   (offline)

Lean labelling design, adjudication, cost estimator + spending guard, GSM1K fetch flag, checker v1.1.1 synonym
tightening, v1.0-style sensitivity rules and refusal counting (2026-11-15).
"""
import csv
import random
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import adjudicate  # noqa: E402
import estimate_cost  # noqa: E402
import make_annotation_sheets as mas  # noqa: E402
import run_phase1  # noqa: E402
from deterministic_checks import check  # noqa: E402
from evaluate import v10_style_decision  # noqa: E402
from report import counts_table  # noqa: E402


def items(n_src=40, gens=("g1", "g2"), repair_every=5):
    out, strata = [], {}
    for i in range(n_src):
        sid = f"s{i:03d}"
        strata[sid] = ("main", ["s<=2", "s=3", "s=4", "s>=5"][i % 4])
        for g in gens:
            for tf in ("plain", "chunked", "naive"):
                oid = f"r|{g}|{tf}|{sid}"
                out.append({"output_id": oid, "source_id": sid, "generator": g, "transformation": tf,
                            "partition": "main", "annotation_id": mas.annotation_id(oid, 2880)})
                if i % repair_every == 0 and tf != "naive":
                    rid = oid + "|repair"
                    out.append({"output_id": rid, "source_id": sid, "generator": g, "transformation": tf,
                                "partition": "main", "repair_of": oid, "annotation_id": mas.annotation_id(rid, 2880)})
        oid = f"r|deterministic|chunked|{sid}"
        out.append({"output_id": oid, "source_id": sid, "generator": "deterministic", "transformation": "chunked",
                    "partition": "main", "annotation_id": mas.annotation_id(oid, 2880)})
    return out, strata


class LeanDesign(unittest.TestCase):
    def setUp(self):
        self.items, self.strata = items()
        self.plan = mas.load_plan(None, "lean")
        self.lab = mas.plan_labelled(self.items, self.plan, random.Random(1), self.strata)
        self.by_aid = {i["annotation_id"]: i for i in self.items}

    def sources(self, gen, tf):
        return {self.by_aid[a]["source_id"] for a in self.lab
                if self.by_aid[a]["generator"] == gen and self.by_aid[a]["transformation"] == tf
                and "repair_of" not in self.by_aid[a]}

    def test_careful_half_paired_across_generators_and_styles(self):
        s = self.sources("g1", "plain")
        self.assertEqual(len(s), 20)
        for g in ("g1", "g2"):
            for tf in ("plain", "chunked"):
                self.assertEqual(self.sources(g, tf), s)

    def test_naive_all_baseline_nested(self):
        self.assertEqual(len(self.sources("g1", "naive")), 40)
        base = self.sources("deterministic", "chunked")
        self.assertEqual(len(base), 12)                      # 0.3 x 40, rounded per stratum (3 of 10 each)
        self.assertTrue(base <= self.sources("g1", "plain"))

    def test_repairs_follow_their_originals(self):
        lab_oids = {self.by_aid[a]["output_id"] for a in self.lab}
        for it in self.items:
            if "repair_of" in it:
                self.assertEqual(it["output_id"] in lab_oids, it["repair_of"] in lab_oids)

    def test_split_annotators_with_shared_double_subset(self):
        lab_items = [self.by_aid[a] for a in self.lab]
        double = mas.pick_double(lab_items, 0.3, random.Random(2))
        assign = mas.split_annotators(lab_items, double, random.Random(3))
        self.assertEqual(set(assign), self.lab)
        self.assertTrue(all(assign[a] == "AB" for a in double))
        a = sum(v == "A" for v in assign.values())
        b = sum(v == "B" for v in assign.values())
        self.assertLessEqual(abs(a - b), len({mas.stratum(i) for i in lab_items}))

    def test_full_design_unchanged_semantics(self):
        plan = mas.load_plan(None, None)
        self.assertEqual(plan["design"], "full")

    def test_config_plan_is_lean(self):
        for f in ("config.matrix.yaml", "config.matrix-budget.yaml", "config.matrix-mid.yaml"):
            plan = mas.load_plan(str(ROOT / f), None)
            self.assertEqual(plan["design"], "lean", f)
            self.assertEqual(plan["label_frac"]["naive"], 1.0)


class Adjudication(unittest.TestCase):
    def write(self, path, rows):
        cols = adjudicate.META + mas.LABEL_COLUMNS
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})

    def row(self, aid, **kw):
        base = {"annotation_id": aid, "transformation_requested": "plain", "model_status": "", "original": "o",
                "adaptation": "a", "math_fidelity": "PASS", "target_preserved": "PASS", "solvability_changed": "NO",
                "ambiguity": "NONE", "leakage_level": "0", "presentation": "2"}
        return {**base, **kw}

    def test_merge_and_resolve(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.write(d / "sheet_A.csv", [self.row("x1"), self.row("x2"), self.row("x3")])
            self.write(d / "sheet_B.csv", [self.row("x2"), self.row("x3", math_fidelity="FAIL"), self.row("x4")])
            final, todo, warn = adjudicate.merge(d / "sheet_A.csv", d / "sheet_B.csv")
            self.assertEqual(sorted(final["annotation_id"]), ["x1", "x2", "x4"])
            self.assertEqual(dict(zip(final["annotation_id"], final["source"])), {"x1": "A", "x2": "agreed", "x4": "B"})
            self.assertEqual(list(todo["annotation_id"]), ["x3"])
            todo.loc[0, [f"{c}_final" for c in adjudicate.KEY_LABELS]] = ["FAIL", "PASS", "NO", "NONE", "0", "2"]
            out, w2 = adjudicate.apply_resolved(final, todo)
            self.assertEqual(len(out), 4)
            self.assertEqual(out.set_index("annotation_id").loc["x3", "source"], "adjudicated")
            self.assertFalse(warn or w2)


class Cost(unittest.TestCase):
    def cfg(self, name):
        return yaml.safe_load((ROOT / name).read_text())

    def test_tiers_order_and_budget_fit(self):
        tot = {f: estimate_cost.estimate(self.cfg(f))["usd"].sum()
               for f in ("config.matrix-budget.yaml", "config.matrix-mid.yaml", "config.matrix.yaml")}
        self.assertLess(tot["config.matrix-budget.yaml"], 9.0)
        self.assertLess(tot["config.matrix-budget.yaml"], tot["config.matrix-mid.yaml"])
        self.assertLess(tot["config.matrix-mid.yaml"], tot["config.matrix.yaml"])
        for f in tot:
            self.assertLessEqual(tot[f], self.cfg(f)["budget_usd"], f)

    def test_pilot_cheaper_and_output_counts(self):
        cfg = self.cfg("config.matrix.yaml")
        t = estimate_cost.estimate(cfg, variance=False, repair_rate=0)
        gen_calls = t[t["step"] == "generate"]["calls"].sum()
        n = sum(estimate_cost.n_sources(cfg["partitions"]).values())
        self.assertEqual(gen_calls, n * 2 * 3)                          # sources x styles x rewriters
        self.assertLess(estimate_cost.estimate(cfg, pilot=True)["usd"].sum(), t["usd"].sum())

    def test_budget_guard(self):
        cfg = self.cfg("config.matrix-budget.yaml")
        c = run_phase1.Ctx(str(ROOT / "config.matrix-budget.yaml"), {**cfg, "run_id": "matrix-budget-v1-guardtest"}, False)
        orig = run_phase1.spent_usd
        run_phase1.spent_usd = lambda _c: 0.0
        self.addCleanup(setattr, run_phase1, "spent_usd", orig)
        self.assertIsNone(run_phase1.budget_check(c, "sheets", 0.01))          # not a paid step
        self.assertIn("BUDGET", run_phase1.budget_check(c, "verify", 0.01) or "")
        self.assertIsNone(run_phase1.budget_check(c, "verify", 100.0))
        cm = run_phase1.Ctx(str(ROOT / "config.matrix-budget.yaml"), cfg, True)
        self.assertIsNone(run_phase1.budget_check(cm, "verify", 0.01))          # mock is free


class FetchFlag(unittest.TestCase):
    def test_gsm1k_fetched_when_partition_used(self):
        calls = []
        cfg = yaml.safe_load((ROOT / "config.matrix.yaml").read_text())
        c = run_phase1.Ctx("config.matrix.yaml", cfg, False)
        c.sh = lambda *a, **k: calls.append(a) or ""
        run_phase1.fetch(c)
        self.assertIn("--gsm1k", calls[0])
        c2 = run_phase1.Ctx("x", {**cfg, "partitions": ["main"]}, False)
        c2.sh = lambda *a, **k: calls.append(a) or ""
        run_phase1.fetch(c2)
        self.assertNotIn("--gsm1k", calls[1])


class Checker(unittest.TestCase):
    SRC = "Tom had 12 apples. He gave 5 to Ann. How many apples remaining does he have?"

    def test_incidental_other_or_left_does_not_mask_lost_remaining(self):
        for cand in ("Tom had 12 apples. He gave 5 to Ann. How many apples does he have? There are other apples.",
                     "Tom had 12 apples. He gave 5 to Ann. Turn left. How many apples does he have?"):
            codes = [f["code"] for f in check(self.SRC, cand)["flags"]]
            self.assertIn("RELATION_OR_QUANTIFIER_LOST", codes, cand)

    def test_quantity_senses_still_count_as_synonyms(self):
        for cand in ("Tom had 12 apples. He gave 5 to Ann. How many apples are left?",
                     "Tom had 12 apples. He gave 5 to Ann. How many apples are left over?"):
            self.assertEqual(check(self.SRC, cand)["decision"], "PASS", cand)

    def test_v10_style_rules(self):
        row = {"decision": "PASS", "deterministic": {"flags": []},
               "program": {"status": "MATCH", "relation_types_equal": False}}
        self.assertEqual(v10_style_decision(row), "REVIEW")
        row2 = {"decision": "REVIEW", "deterministic": {"flags": [{"code": "NUMBER_WORD_ADDED"}]}, "program": {}}
        self.assertEqual(v10_style_decision(row2), "REJECT")
        self.assertEqual(v10_style_decision({"decision": "PASS", "deterministic": {"flags": []}, "program": {}}), "PASS")


class Refusals(unittest.TestCase):
    def test_counts_table_has_refusals(self):
        g = pd.DataFrame([{"kind": "main", "output_id": "a", "generator": "g", "transformation": "naive",
                           "status": "FREE_TEXT", "parse_error": False, "api_error": False, "refusal": True,
                           "empty": False},
                          {"kind": "main", "output_id": "b", "generator": "g", "transformation": "naive",
                           "status": "FREE_TEXT", "parse_error": False, "api_error": False, "refusal": False,
                           "empty": False}])
        t = counts_table(g)
        self.assertEqual(int(t["refusal"].iloc[0]), 1)


if __name__ == "__main__":
    unittest.main()
