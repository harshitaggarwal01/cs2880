"""Run: python -m unittest tests.test_phase1_pipeline -v   (offline; mock provider only)

Mock runs use a throwaway run_id ("p1test-*"), so they never touch main-v1-mock; folders are removed afterwards.
"""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseline import records  # noqa: E402
from common import read_jsonl, write_jsonl  # noqa: E402
from deterministic_checks import check  # noqa: E402
from ledger import build_ledger, per_item_cost, price_call, summarize  # noqa: E402
from run_phase1 import STEPS, run  # noqa: E402
from verify import ALL_LAYERS, decide, decide_subset  # noqa: E402

FROZEN = ROOT / "data" / "frozen"


class Phase1Case(unittest.TestCase):
    def make_cfg(self, run_id: str) -> tuple[str, Path]:
        """Copy of config.example.yaml with its own run_id; returns (config path, mock run dir)."""
        cfg = yaml.safe_load((ROOT / "config.example.yaml").read_text())
        cfg["run_id"] = run_id
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for d in (ROOT / "data" / "outputs" / f"{run_id}-mock", ROOT / "data" / "annotations" / f"{run_id}-mock",
                  ROOT / "data" / "annotations" / run_id):
            shutil.rmtree(d, ignore_errors=True)
            self.addCleanup(shutil.rmtree, d, True)
        path = tmp / "config.yaml"
        path.write_text(yaml.safe_dump(cfg))
        return str(path), ROOT / "data" / "outputs" / f"{run_id}-mock"

    @staticmethod
    def sh(*args: str) -> str:
        return subprocess.run([sys.executable, *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


class Baseline(Phase1Case):
    def test_baseline_records_pass_verify_and_sheets(self):
        cfg, _ = self.make_cfg("p1test-base")
        srcs = read_jsonl(FROZEN / "dev.jsonl")
        rows = records(srcs, "p1test-base")
        self.assertEqual(len(rows), len(srcs))
        required = {"output_id", "run_id", "generator", "transformation", "source_id", "dataset", "partition",
                    "source_sha256", "prompt_version", "prompt_sha256", "provider", "requested_model", "returned_model",
                    "response_id", "usage", "latency_s", "timestamp", "raw_output", "status", "adapted_problem",
                    "parse_error"}
        for r in rows:
            self.assertTrue(required <= set(r))
            self.assertEqual(r["output_id"], f"p1test-base|deterministic|chunked|{r['source_id']}")
            self.assertEqual((r["generator"], r["status"], r["parse_error"]), ("deterministic", "DETERMINISTIC", False))
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        path = tmp / "baseline.jsonl"
        write_jsonl(path, rows)
        self.sh("src/verify.py", str(path), "--config", cfg, "--mock")
        ver = read_jsonl(tmp / "baseline.verify-det.jsonl")  # det-only by default
        self.assertEqual(len(ver), len(rows))
        for v in ver:
            self.assertNotEqual(v["decision"], "REJECT")
            self.assertEqual((v["layers"], v["critic"], v["program"]), (["det"], None, None))
        self.sh("src/make_annotation_sheets.py", str(path))
        self.assertTrue((ROOT / "data" / "annotations" / "p1test-base" / "sheet_A.csv").exists())


class Ledger(Phase1Case):
    PRICES = {"gpt-6-luna": {"in": 1.0, "out": 4.0}, "gpt-6": {"in": 9.0, "out": 9.0}}

    def test_ledger_prices_thinking_tokens(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 500_000, "thinking_tokens": 500_000}
        self.assertAlmostEqual(price_call(usage, "gpt-6-luna", self.PRICES), 1.0 + 4.0)
        self.assertAlmostEqual(price_call({"input_tokens": 10, "output_tokens": None}, "gpt-6-luna", self.PRICES), 1e-5)
        # prefix match picks the longest key
        self.assertAlmostEqual(price_call(usage, "gpt-6-luna-2026-09-22", self.PRICES), 5.0)
        self.assertAlmostEqual(price_call(usage, "gpt-6-terra", self.PRICES), 18.0)
        self.assertEqual(price_call(usage, "mystery-model", self.PRICES), 0.0)
        self.assertEqual(price_call(usage, None, self.PRICES), 0.0)
        self.assertEqual(price_call(None, "gpt-6-luna", self.PRICES), 0.0)

    def test_ledger_totals_match_generations(self):
        cfg, run_dir = self.make_cfg("p1test-ledger")
        self.sh("src/collect_outputs.py", "--config", cfg, "--pilot", "--mock")
        gens = read_jsonl(run_dir / "pilot_generations.jsonl")
        ledger = build_ledger(run_dir, yaml.safe_load(Path(cfg).read_text()))
        self.assertEqual(int((ledger["stage"] == "gen").sum()), len(gens))
        self.assertTrue((run_dir / "ledger.csv").exists())
        self.assertEqual(int(summarize(ledger).query("group == 'total'")["calls"].iloc[0]), len(ledger))
        self.assertEqual(set(per_item_cost(ledger)), {g["output_id"] for g in gens})

    def test_per_item_cost_folds_repairs(self):
        import pandas as pd
        led = pd.DataFrame([
            {"output_id": "r|a|plain|s1", "stage": "gen", "usd": 1.0}, {"output_id": "r|a|plain|s1", "stage": "critic", "usd": 0.5},
            {"output_id": "r|a|plain|s1|repair1", "stage": "repair", "usd": 0.25},
            {"output_id": "r|a|plain|s1", "stage": "variance", "usd": 9.0}])
        self.assertEqual(per_item_cost(led), {"r|a|plain|s1": 1.75})


class Verify(Phase1Case):
    def test_decide_subset_matches_full(self):
        cfg, run_dir = self.make_cfg("p1test-verify")
        self.sh("src/collect_outputs.py", "--config", cfg, "--pilot", "--mock")
        gens = run_dir / "pilot_generations.jsonl"
        self.sh("src/verify.py", str(gens), "--config", cfg, "--mock")
        full = read_jsonl(run_dir / "pilot_generations.verify-critic-det-program.jsonl")
        self.assertEqual(len(full), len(read_jsonl(gens)))
        for v in full:
            self.assertEqual(decide_subset(v, ALL_LAYERS), (v["decision"], v["reasons"]))
            self.assertEqual(decide_subset(v, {"det"}), decide(v["deterministic"], None, None, require_critic=False))
            if not v["deterministic"]["flags"]:
                self.assertEqual(decide_subset(v, {"det"})[0], "PASS")
            self.assertEqual(set(v["extract_meta"]), {"source", "candidate"})
        # extraction cache: one row per distinct text, keyed by sha256
        cache = read_jsonl(run_dir / "extractions.jsonl")
        self.assertEqual(len({c["key"] for c in cache}), len(cache))
        # offline --layers subset: no API layers, rows derived from the full file
        self.sh("src/verify.py", str(gens), "--config", cfg, "--layers", "det,critic")
        sub = read_jsonl(run_dir / "pilot_generations.verify-critic-det.jsonl")
        self.assertEqual(len(sub), len(full))
        for v, s in zip(full, sub):
            self.assertEqual(s["derived_from"], "pilot_generations.verify-critic-det-program.jsonl")
            self.assertEqual((s["decision"], s["reasons"]), decide_subset(v, {"det", "critic"}))
            self.assertIsNone(s["program"])
        # derived rows must not be billed twice
        led = build_ledger(run_dir, yaml.safe_load(Path(cfg).read_text()))
        self.assertEqual(int((led["stage"] == "critic").sum()), len(full))


class Orchestrator(Phase1Case):
    def test_orchestrator_resume_skips_done_steps(self):
        cfg, run_dir = self.make_cfg("p1test-orch")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run(cfg, None, "baseline", mock=True, force=False)
        for step in ("pilot", "generate", "ablation", "baseline"):
            self.assertTrue((run_dir / ".done" / step).exists(), step)
        self.assertTrue((run_dir / "config.frozen.yaml").exists())
        stamps = {p.name: p.stat().st_mtime_ns for p in (run_dir / ".done").iterdir()}
        n_gen = len(read_jsonl(run_dir / "generations.jsonl"))
        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            run(cfg, None, "baseline", mock=True, force=False)
        self.assertEqual(out2.getvalue().count("skipped (already done)"), 4)
        self.assertEqual(stamps, {p.name: p.stat().st_mtime_ns for p in (run_dir / ".done").iterdir()})
        self.assertEqual(len(read_jsonl(run_dir / "generations.jsonl")), n_gen)
        self.assertEqual(yaml.safe_load((run_dir / "config.frozen.yaml").read_text())["run_id"], "p1test-orch-mock")

    def test_list_prints_steps(self):
        out = self.sh("src/run_phase1.py", "--list")
        for name, _ in STEPS:
            self.assertIn(name, out)
        self.assertEqual([n for n, _ in STEPS][:3], ["fetch", "pilot", "generate"])


if __name__ == "__main__":
    unittest.main()
