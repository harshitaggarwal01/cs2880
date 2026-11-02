"""Run: python -m unittest discover -s tests -v   (from the repo root)

Offline tests for the Phase-1 analysis code (evaluate.py additions, report.py, variance_check.py) on SYNTHETIC data.
Nothing here is a measured result.
"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import evaluate as ev  # noqa: E402
import report  # noqa: E402
import variance_check as vc  # noqa: E402
from verify import decide  # noqa: E402

B_TEST = 100


def labels_frame(rng, n_sources=30) -> pd.DataFrame:
    """Two generators x plain/chunked/naive, plus the deterministic chunked baseline (always safe)."""
    rows = []
    p_safe = {("gA", "plain"): 0.9, ("gA", "chunked"): 0.95, ("gA", "naive"): 0.2,
              ("gB", "plain"): 0.6, ("gB", "chunked"): 0.9, ("gB", "naive"): 0.5}
    for i in range(n_sources):
        sid = f"gsm8k-train-{i:04d}"
        for (g, tf), p in p_safe.items():
            rows.append({"source_id": sid, "model": g, "transformation": tf, "SAFE": int(rng.random() < p)})
        rows.append({"source_id": sid, "model": "deterministic", "transformation": "chunked", "SAFE": 1})
    return pd.DataFrame(rows)


class Families(unittest.TestCase):
    def test_families_exactly_three_and_holm_within_family(self):
        df = labels_frame(np.random.default_rng(1))
        fam = ev.prespecified_families(df, "SAFE", b=B_TEST)
        self.assertEqual(set(fam["family"]), {"realistic_vs_constrained_chunked", "generator_A_vs_B", "plain_vs_chunked"})
        self.assertEqual(list(fam.columns), ["family", "comparison", "n_pairs", "diff", "ci_lo", "ci_hi", "A_only",
                                             "B_only", "mcnemar_p", "holm_p"])
        self.assertFalse(fam["comparison"].str.contains("deterministic").any())
        # F1 per generator (2), F2 per transformation (3), F3 per generator (2)
        self.assertEqual(fam["family"].value_counts().to_dict(),
                         {"generator_A_vs_B": 3, "realistic_vs_constrained_chunked": 2, "plain_vs_chunked": 2})
        for _, g in fam.groupby("family"):
            np.testing.assert_allclose(g["holm_p"], ev.holm(g["mcnemar_p"].tolist()))
        pooled = ev.holm(fam["mcnemar_p"].tolist())
        self.assertFalse(np.allclose(pooled, fam["holm_p"]), "Holm must not be pooled across families")
        # planted effect: gA naive is far less safe than gA chunked, so A - B < 0 with a small p
        row = fam[fam["comparison"] == "gA: naive vs chunked"].iloc[0]
        self.assertLess(row["diff"], -0.4)
        self.assertLess(row["mcnemar_p"], 0.01)

    def test_skips_comparisons_with_under_two_pairs(self):
        df = labels_frame(np.random.default_rng(2), n_sources=1)
        self.assertEqual(len(ev.prespecified_families(df, "SAFE", b=B_TEST)), 0)


class Presentation(unittest.TestCase):
    def frame(self, shift: float) -> tuple[pd.DataFrame, dict]:
        rng = np.random.default_rng(3)
        rows, sources = [], {}
        for i in range(40):
            sid = f"gsm8k-train-{i:04d}"
            base = float(rng.integers(0, 3))
            sources[sid] = {"text": " ".join(["word"] * (10 + i)), "n_steps": 1 + i % 6, "dataset": "gsm8k"}
            rows.append({"source_id": sid, "model": "deterministic", "transformation": "chunked", "presentation": base})
            rows.append({"source_id": sid, "model": "gA", "transformation": "chunked",
                         "presentation": base + shift if shift else base})
            rows.append({"source_id": sid, "model": "gA", "transformation": "plain", "presentation": 1.0})
        rows.append({"source_id": "gsm8k-train-0000", "model": "gA", "transformation": "chunked", "presentation": np.nan})
        return pd.DataFrame(rows), sources

    def test_presentation_wilcoxon_sign(self):
        df, sources = self.frame(shift=1.0)
        out = ev.presentation_vs_baseline(df, b=B_TEST, sources=sources)
        overall = out[out["stratum_type"] == "overall"].iloc[0]
        self.assertEqual(overall["n_pairs"], 40)
        self.assertGreater(overall["diff"], 0)
        self.assertLess(overall["wilcoxon_p"], 0.05)
        self.assertGreater(overall["ci_lo"], 0)
        self.assertEqual(set(out["stratum_type"]), {"overall", "step_bucket", "length_tercile"})
        self.assertEqual(len(ev.presentation_vs_baseline(df, b=B_TEST)), 1)  # no sources -> no strata

    def test_all_zero_differences_are_handled(self):
        df, _ = self.frame(shift=0.0)
        out = ev.presentation_vs_baseline(df, b=B_TEST)
        self.assertEqual(out.iloc[0]["wilcoxon_p"], 1.0)
        self.assertEqual(out.iloc[0]["diff"], 0.0)


class Logit(unittest.TestCase):
    def sources_and_labels(self, deterministic: bool):
        rng = np.random.default_rng(4)
        sources, rows = {}, []
        for i in range(300):
            sid = f"gsm8k-train-{i:04d}"
            n = int(rng.integers(1, 9))
            sources[sid] = {"text": ("She has 5 apples. " + "word " * int(rng.integers(5, 40)) + "How many?"), "n_steps": n,
                            "dataset": "gsm8k"}
            for tf, shift in (("plain", 0.0), ("chunked", -0.5)):
                p = 1 / (1 + np.exp(-(-1.0 + 0.7 * (n - 4) + shift)))
                unsafe = int(n > 4) if deterministic else int(rng.random() < p)
                rows.append({"source_id": sid, "model": "gA", "transformation": tf, "SAFE": 1 - unsafe})
        return sources, pd.DataFrame(rows)

    def test_logit_cluster_on_synthetic(self):
        sources, df = self.sources_and_labels(deterministic=False)
        res = ev.logit_unsafe(df, sources)
        self.assertFalse(res["penalized"])
        self.assertTrue(res["converged"])
        self.assertEqual(res["n"], 600)
        row = res["table"].set_index("term").loc["n_steps"]
        self.assertGreater(row["coef"], 0.3)
        self.assertLess(row["p"], 0.01)
        self.assertAlmostEqual(row["odds_ratio"], np.exp(row["coef"]))
        self.assertTrue(np.isfinite(row["se"]))

    def test_penalized_fallback_on_separable_data(self):
        sources, df = self.sources_and_labels(deterministic=True)
        res = ev.logit_unsafe(df, sources)
        self.assertTrue(res["penalized"])
        self.assertFalse(res["converged"])
        t = res["table"].set_index("term")
        self.assertGreater(t.loc["n_steps", "coef"], 0)
        self.assertTrue(np.isnan(t.loc["n_steps", "se"]))


def verify_row(oid, det_flags, critic, program) -> dict:
    det_decision = "REJECT" if any(f["severity"] == "REJECT" for f in det_flags) else "REVIEW" if det_flags else "PASS"
    det = {"decision": det_decision, "flags": det_flags,
           "readability": {"source_fkgl": 6.0, "candidate_fkgl": 5.0}}
    decision, reasons = decide(det, critic, program)
    return {"output_id": oid, "layers": ["critic", "det", "program"], "decision": decision, "reasons": reasons,
            "deterministic": det, "critic": critic, "program": program}


SAFE_CRITIC = {"overall": "SAFE", "failure_codes": [], "math_fidelity": "PASS", "instructional_leakage": "NONE"}
MATCH = {"status": "MATCH", "relation_types_equal": True}


class LayerAblations(unittest.TestCase):
    def setUp(self):
        review = [{"code": "LENGTH_EXPANDED", "severity": "REVIEW", "detail": ""}]
        reject = [{"code": "QTY_ADD", "severity": "REJECT", "detail": ""}]
        self.rows = [
            verify_row("A", reject, SAFE_CRITIC, MATCH),
            verify_row("B", [], {"overall": "UNSAFE", "failure_codes": ["QTY_CHANGE"], "math_fidelity": "FAIL",
                                 "instructional_leakage": "NONE"}, MATCH),
            verify_row("C", [], SAFE_CRITIC, MATCH),
            verify_row("D", review, SAFE_CRITIC, MATCH),
            verify_row("E", [], SAFE_CRITIC, {"status": "MISMATCH"}),
        ]
        self.labels = pd.DataFrame({
            "output_id": list("ABCDE"), "source_id": [f"s{i}" for i in range(5)],
            "transformation": ["naive", "chunked", "chunked", "plain", "plain"], "SAFE": [0, 0, 1, 1, 0]})

    def test_full_layer_set_reproduces_stored_decision(self):
        for r in self.rows:
            self.assertEqual(ev.subset_decision(r, {"det", "critic", "program"})[0], r["decision"])
        self.assertEqual([r["decision"] for r in self.rows], ["REJECT", "REJECT", "PASS", "REVIEW", "REJECT"])
        det_only = [ev.subset_decision(r, {"det"})[0] for r in self.rows]
        self.assertEqual(det_only, ["REJECT", "PASS", "PASS", "REVIEW", "PASS"])

    def test_layer_ablations_equal_online_decide(self):
        abl = ev.layer_ablations(self.rows, self.labels, b=20)
        self.assertEqual(set(abl["layers"]), set(ev.LAYER_SETS))
        self.assertEqual(set(abl["subset"]), {"realistic", "constrained", "overall"})

        def cell(layers, op, subset="overall"):
            return abl[(abl["layers"] == layers) & (abl["operating_point"] == op) & (abl["subset"] == subset)].iloc[0]

        full_rej, full_any = cell("det+critic+program", "FLAG_REJECT"), cell("det+critic+program", "FLAG_ANY")
        self.assertEqual((full_rej["tp"], full_rej["fn"], full_rej["fp"], full_rej["tn"]), (3, 0, 0, 2))
        self.assertEqual((full_any["tp"], full_any["fn"], full_any["fp"], full_any["tn"]), (3, 0, 1, 1))
        self.assertAlmostEqual(full_any["flag_rate"], 4 / 5)
        det_rej, det_any = cell("det", "FLAG_REJECT"), cell("det", "FLAG_ANY")
        self.assertEqual((det_rej["tp"], det_rej["fn"], det_rej["fp"], det_rej["tn"]), (1, 2, 0, 2))
        self.assertEqual((det_any["tp"], det_any["fn"], det_any["fp"], det_any["tn"]), (1, 2, 1, 1))
        self.assertAlmostEqual(det_rej["recall_unsafe"], 1 / 3)
        real = cell("det+critic+program", "FLAG_REJECT", "realistic")
        self.assertEqual(real["tp"] + real["fn"] + real["fp"] + real["tn"], 1)

    def test_rows_without_a_layer_are_skipped(self):
        det_only_rows = [{**r, "layers": ["det"], "critic": None, "program": None} for r in self.rows]
        abl = ev.layer_ablations(det_only_rows, self.labels, b=20)
        self.assertEqual(set(abl["layers"]), {"det"})


class Repair(unittest.TestCase):
    def test_repair_outcomes_counts(self):
        # (id, generator, SAFE, SAU, presentation, repair_of)
        spec = [("o1", "gA", 0, 0, 0, None), ("o2", "gA", 1, 1, 3, None), ("o3", "gA", 0, 0, 1, None),
                ("o4", "gB", 1, 1, 2, None), ("o5", "gB", 1, 1, 2, None), ("o6", "gB", 0, 0, 1, None),
                ("b1", "deterministic", 1, 1, 2, None),
                ("o1|repair1", "gA", 1, 1, 3, "o1"), ("o2|repair1", "gA", 0, 0, 1, "o2"),
                ("o3|repair1", "gA", 0, 0, 1, "o3"), ("o4|repair1", "gB", 1, 1, 2, "o4"),
                ("o6|repair1", "gB", 1, 1, 2, "o6")]
        labels = pd.DataFrame([{"annotation_id": f"a{i}", "SAFE": s, "SAFE_AND_USEFUL": u, "presentation": p}
                               for i, (_, _, s, u, p, _) in enumerate(spec)])
        key = pd.DataFrame([{"annotation_id": f"a{i}", "output_id": oid, "generator": g, "is_repair": r is not None,
                             "repair_of": r} for i, (oid, g, _, _, _, r) in enumerate(spec)])
        out = ev.repair_outcomes(labels, key)
        self.assertEqual((out["n_originals"], out["n_repaired"]), (6, 5))
        self.assertEqual((out["unsafe_to_safe"], out["safe_to_unsafe"], out["unchanged"]), (2, 1, 2))
        self.assertAlmostEqual(out["mean_delta_presentation"], (3 - 0 + 1 - 3 + 1 - 1 + 2 - 2 + 2 - 1) / 5)
        self.assertAlmostEqual(out["safe_per100_before"], 100 * 3 / 6)
        self.assertAlmostEqual(out["safe_per100_after"], 100 * 4 / 6)
        self.assertAlmostEqual(out["safe_useful_per100_before"], 100 * 3 / 6)
        self.assertAlmostEqual(out["safe_useful_per100_after"], 100 * 4 / 6)
        self.assertEqual({g["generator"] for g in out["by_generator"]}, {"gA", "gB"})

    def test_write_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = ev.write_analysis(Path(d), "t", pd.DataFrame({"a": [1]}))
            p2 = ev.write_analysis(Path(d), "r", {"x": np.int64(3), "y": float("nan"), "df": pd.DataFrame({"a": [1]})})
            self.assertEqual(p1.name, "t.csv")
            self.assertEqual(json.loads(p2.read_text()), {"x": 3, "y": None, "df": [{"a": 1}]})


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def fake_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    common = {"run_id": "r1", "partition": "main", "dataset": "gsm8k", "parse_error": False}
    write_jsonl(run_dir / "generations.jsonl", [
        {**common, "output_id": "r1|gA|chunked|s1", "generator": "gA", "transformation": "chunked", "source_id": "s1",
         "status": "REWRITTEN", "adapted_problem": "- Ann has 3 pens.\nQuestion: How many?"},
        {**common, "output_id": "r1|gA|plain|s1", "generator": "gA", "transformation": "plain", "source_id": "s1",
         "status": "NO_REWRITE_NEEDED", "adapted_problem": "Ann has 3 pens. How many?"}])
    write_jsonl(run_dir / "ablation_generations.jsonl", [
        {**common, "output_id": "r1|gA|naive|s1", "generator": "gA", "transformation": "naive", "source_id": "s1",
         "status": "FREE_TEXT", "adapted_problem": "Ann has 3 pens."}])
    write_jsonl(run_dir / "baseline_main.jsonl", [
        {"source_id": "s1", "generator": "deterministic", "transformation": "chunked", "adapted_problem": "- Ann has 3 pens."}])
    write_jsonl(run_dir / "repairs.jsonl", [
        {**common, "output_id": "r1|gA|naive|s1|repair1", "repair_of": "r1|gA|naive|s1", "generator": "gA",
         "transformation": "naive", "source_id": "s1", "adapted_problem": "Ann has 3 pens."}])
    flag = {"code": "QTY_ADD", "severity": "REJECT", "detail": "x"}
    write_jsonl(run_dir / "generations.verify-det.jsonl", [
        {"output_id": "r1|gA|chunked|s1", "layers": ["det"], "decision": "PASS", "reasons": [],
         "deterministic": {"decision": "PASS", "flags": [],
                           "readability": {"source_fkgl": 6.0, "candidate_fkgl": 4.0}}},
        {"output_id": "r1|gA|naive|s1", "layers": ["det"], "decision": "REJECT", "reasons": ["det:QTY_ADD"],
         "deterministic": {"decision": "REJECT", "flags": [flag],
                           "readability": {"source_fkgl": 6.0, "candidate_fkgl": 7.5}}}])
    (run_dir / "ledger.csv").write_text(
        "output_id,stage,generator,transformation,partition,model,input_tokens,output_tokens,thinking_tokens,usd,latency_s,timestamp\n"
        "r1|gA|chunked|s1,gen,gA,chunked,main,m,100,50,0,0.01,1.0,t\n"
        "r1|gA|chunked|s1,critic,gA,chunked,main,c,200,80,0,0.02,2.0,t\n"
        "r1|gA|naive|s1,gen,gA,naive,main,m,90,40,0,0.01,1.0,t\n")


class Report(unittest.TestCase):
    def test_report_pipeline_mode_writes_md_and_figures(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir, out_md, fig_dir = Path(d) / "run" / "r1", Path(d) / "docs" / "r1_report.md", Path(d) / "docs" / "figs"
            fake_run(run_dir)
            report.build(run_dir, None, None, out_md, fig_dir)
            text = out_md.read_text()
            pngs = sorted(p.name for p in fig_dir.glob("*.png"))
            self.assertTrue(out_md.exists())
            self.assertGreaterEqual(len(pngs), 3, pngs)
            self.assertIn("![", text)
            self.assertIn("QTY_ADD", text)
            self.assertIn("figs/fig_flags.png", text)  # relative link
            self.assertIn("no human labels", text)
            self.assertIn("delta_fkgl", text)

    def test_report_labelled_mode_smoke(self):
        rng = np.random.default_rng(5)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            run_dir = d / "r2"
            run_dir.mkdir()
            sources, labels, key, gens, ver = {}, [], [], [], []
            for i in range(12):
                sid = f"gsm8k-train-{i:04d}"
                sources[sid] = {"text": "Ann has 3 pens and 4 more than Bo. How many?" + " x" * i, "n_steps": 1 + i % 4,
                                "dataset": "gsm8k"}
                for gen, tf in (("gA", "plain"), ("gA", "chunked"), ("deterministic", "chunked")):
                    oid = f"r2|{gen}|{tf}|{sid}"
                    aid = f"a{len(labels)}"
                    ok = gen == "deterministic" or rng.random() < 0.7
                    labels.append({"annotation_id": aid, "annotator": "ADJ", "math_fidelity": "PASS" if ok else "FAIL",
                                   "target_preserved": "PASS", "solvability_changed": "NO", "ambiguity": "NONE",
                                   "leakage_level": 0, "presentation": int(rng.integers(0, 4)),
                                   "abstention_appropriate": "NA", "failure_codes": ""})
                    key.append({"annotation_id": aid, "output_id": oid, "source_id": sid, "generator": gen,
                                "transformation": tf, "partition": "main", "is_repair": False, "repair_of": "",
                                "double_annotated": False})
                    gens.append({"output_id": oid, "generator": gen, "transformation": tf, "source_id": sid,
                                 "status": "REWRITTEN", "adapted_problem": "x"})
                    flags = [] if ok else [{"code": "QTY_ADD", "severity": "REJECT", "detail": ""}]
                    ver.append(verify_row(oid, flags, SAFE_CRITIC, MATCH))
            write_jsonl(run_dir / "generations.jsonl", gens)
            write_jsonl(run_dir / "generations.verify-critic-det-program.jsonl", ver)
            pd.DataFrame(labels).to_csv(d / "adjudicated.csv", index=False)
            pd.DataFrame(key).to_csv(d / "KEY_DO_NOT_OPEN.csv", index=False)
            report.build(run_dir, d / "adjudicated.csv", d / "KEY_DO_NOT_OPEN.csv", d / "out" / "rep.md", d / "out" / "figs",
                         sources=sources, b=30)
            text = (d / "out" / "rep.md").read_text()
            for heading in ("Outcome rates", "Prespecified paired comparisons", "Presentation versus", "layer ablations",
                            "Constrained repair", "logistic regression"):
                self.assertIn(heading.lower(), text.lower())
            names = {p.name for p in (d / "out" / "figs").glob("*.png")}
            self.assertTrue({"fig_rates.png", "fig_verifier.png", "fig_presentation.png"} <= names, names)


class Variance(unittest.TestCase):
    def gens(self, tag: str, texts: dict) -> list[dict]:
        return [{"output_id": f"{tag}|{g}|{tf}|{s}", "generator": g, "transformation": tf, "source_id": s,
                 "adapted_problem": t} for (g, tf, s), t in texts.items()]

    def test_variance_flip_rates(self):
        texts_o = {("gA", "plain", "s1"): "Ann has 3 pens.", ("gA", "plain", "s2"): "Bo has 4 cups.",
                   ("gA", "chunked", "s1"): "- Ann has 3 pens.", ("gB", "plain", "s1"): "Cy has 5 hats."}
        texts_r = {("gA", "plain", "s1"): "Ann  has 3 pens.", ("gA", "plain", "s2"): "Bo owns 4 cups and 9 hats.",
                   ("gA", "chunked", "s1"): "- Ann has 3 pens.", ("gB", "plain", "s1"): "Cy has 6 hats."}
        orig, regen = self.gens("o", texts_o), self.gens("o-var", texts_r)

        def v(oid, det, full, layers):
            return {"output_id": oid, "layers": layers, "decision": full, "deterministic": {"decision": det, "flags": []}}

        v_orig = [v("o|gA|plain|s1", "PASS", "PASS", ["det", "critic"]), v("o|gA|plain|s2", "PASS", "PASS", ["det", "critic"]),
                  v("o|gA|chunked|s1", "PASS", "REVIEW", ["det", "critic"]), v("o|gB|plain|s1", "PASS", "PASS", ["det", "critic"])]
        v_regen = [v("o-var|gA|plain|s1", "PASS", "PASS", ["det"]), v("o-var|gA|plain|s2", "REJECT", "REJECT", ["det"]),
                   v("o-var|gA|chunked|s1", "PASS", "PASS", ["det"]), v("o-var|gB|plain|s1", "PASS", "PASS", ["det"])]
        r = vc.flip_rates(orig, regen, v_orig, v_regen)
        self.assertEqual(r["overall"]["n_pairs"], 4)
        self.assertAlmostEqual(r["overall"]["text_identical_rate"], 2 / 4)       # whitespace-normalised
        self.assertAlmostEqual(r["overall"]["det_decision_flip_rate"], 1 / 4)
        self.assertTrue(np.isnan(r["overall"]["full_decision_flip_rate"]))     # layer sets differ: not comparable
        self.assertEqual(set(r["by_condition"]), {"gA|plain", "gA|chunked", "gB|plain"})
        self.assertAlmostEqual(r["by_condition"]["gA|plain"]["text_identical_rate"], 1 / 2)
        self.assertAlmostEqual(r["by_condition"]["gA|plain"]["det_decision_flip_rate"], 1 / 2)

        v_regen_full = [{**x, "layers": ["det", "critic"]} for x in v_regen]
        r2 = vc.flip_rates(orig, regen, v_orig, v_regen_full)
        self.assertAlmostEqual(r2["overall"]["full_decision_flip_rate"], 2 / 4)  # gA plain s2 and gA chunked s1

    def test_pick_is_seeded_and_flip_sheet_is_blinded(self):
        srcs = [{"source_id": f"s{i:03d}", "text": f"t{i}"} for i in range(50)]
        a, b = vc.pick(srcs, n=20, seed=7), vc.pick(list(reversed(srcs)), n=20, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 20)
        self.assertEqual(len(vc.pick(srcs[:5], n=20)), 5)
        orig = self.gens("o", {("gA", "plain", "s1"): "Ann has 3 pens.", ("gA", "plain", "s2"): "same"})
        regen = self.gens("o-var", {("gA", "plain", "s1"): "Ann owns 3 pens.", ("gA", "plain", "s2"): "same"})
        with tempfile.TemporaryDirectory() as d:
            path = vc.make_flip_sheet(orig, regen, {"s1": "Ann has 3 pens. How many?", "s2": "x"}, Path(d) / "sheet.csv")
            rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
            key = list(csv.DictReader((Path(d) / "sheet_KEY.csv").read_text(encoding="utf-8").splitlines()))
        self.assertEqual(len(rows), 1)  # identical text is not worth a human check
        self.assertNotIn("generator", rows[0])
        self.assertEqual({rows[0]["adaptation_X"], rows[0]["adaptation_Y"]}, {"Ann has 3 pens.", "Ann owns 3 pens."})
        self.assertIn(key[0]["X_is"], {"original", "regenerated"})


if __name__ == "__main__":
    unittest.main()
