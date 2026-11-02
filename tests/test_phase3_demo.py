"""Run: python -m unittest tests.test_phase3_demo -v   (offline; no streamlit server, no API key)"""
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from demo import core  # noqa: E402

PROBLEM = "Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def fake_run(tmp: Path) -> tuple[Path, Path, str]:
    """One dev source, two generations, one verify row (det+critic+program), a two-row ledger."""
    src = json.loads((ROOT / "data" / "frozen" / "dev.jsonl").read_text(encoding="utf-8").splitlines()[0])
    frozen, run = tmp / "frozen", tmp / "run-v1"
    frozen.mkdir()
    run.mkdir()
    write_jsonl(frozen / "dev.jsonl", [src])
    sid = src["source_id"]
    gens = [{"output_id": f"run-v1|haiku|{t}|{sid}", "run_id": "run-v1", "generator": "haiku", "transformation": t,
             "source_id": sid, "partition": "dev", "status": "NO_REWRITE_NEEDED", "adapted_problem": src["text"]}
            for t in ("plain", "chunked")]
    write_jsonl(run / "generations.jsonl", gens)
    det = {"decision": "REVIEW", "flags": [{"code": "UNIT_SET_CHANGED", "severity": "REVIEW", "detail": "x"}],
           "readability": {"source_fkgl": 6.0, "candidate_fkgl": 5.0, "source_words": 22, "candidate_words": 22,
                           "candidate_max_sentence_words": 15}}
    write_jsonl(run / "generations.verify-critic-det-program.jsonl",
                [{"output_id": gens[0]["output_id"], "layers": ["critic", "det", "program"], "decision": "REVIEW",
                  "reasons": ["det:UNIT_SET_CHANGED"], "deterministic": det,
                  "critic": {"overall": "SAFE", "failure_codes": []}, "program": {"status": "MATCH"}}])
    pd.DataFrame([{"output_id": gens[0]["output_id"], "stage": "gen", "usd": 0.002},
                  {"output_id": gens[0]["output_id"], "stage": "critic", "usd": 0.005}]).to_csv(run / "ledger.csv", index=False)
    return run, frozen, sid


class DemoCase(unittest.TestCase):
    def test_demo_offline_index_loads(self):
        with tempfile.TemporaryDirectory() as t:
            run, frozen, sid = fake_run(Path(t))
            idx = core.load_run(run, frozen_dir=frozen)
            self.assertEqual(set(idx), {"run_dir", "sources", "gens", "verify", "by_source", "ledger"})
            self.assertIn(sid, idx["sources"])
            self.assertEqual(len(idx["gens"]), 2)
            self.assertEqual(len(idx["verify"]), 1)
            self.assertEqual(len(idx["by_source"][sid]), 2)
            self.assertEqual(len(idx["ledger"]), 2)
            view = core.offline_view(idx, sid)
            self.assertEqual([v["transformation"] for v in view], ["chunked", "plain"])
            chunked, plain = view
            for key in ("output_id", "generator", "transformation", "adapted_problem", "decision", "reasons", "flags",
                        "risk_score", "cost"):
                self.assertIn(key, plain)
            self.assertEqual(plain["decision"], "REVIEW")
            self.assertEqual(plain["reasons"], ["det:UNIT_SET_CHANGED"])
            self.assertEqual(plain["flags"][0]["code"], "UNIT_SET_CHANGED")
            self.assertAlmostEqual(plain["cost"], 0.007)
            self.assertIsNone(chunked["decision"])      # no verify row stored for this output
            self.assertAlmostEqual(chunked["cost"], 0.0)
            self.assertTrue(plain["risk_score"] is None or plain["risk_score"] >= 0)
            self.assertEqual(core.offline_view(idx, "nope"), [])

    def test_offline_view_without_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            run, frozen, sid = fake_run(Path(t))
            (run / "ledger.csv").unlink()
            idx = core.load_run(run, frozen_dir=frozen)
            self.assertIsNone(idx["ledger"])
            self.assertTrue(all(v["cost"] is None for v in core.offline_view(idx, sid)))

    def test_live_check_passes_identity(self):
        res = core.live_check(PROBLEM, PROBLEM, "plain")
        self.assertEqual(res["decision"], "PASS")
        self.assertEqual(res["reasons"], [])
        self.assertEqual(res["flags"], [])
        self.assertIn("candidate_fkgl", res["readability"])
        self.assertEqual(core.verdict_badge("PASS"), "✅ PASS")

    def test_live_check_rejects_changed_number(self):
        res = core.live_check(PROBLEM, PROBLEM.replace("48", "84"), "plain")
        self.assertEqual(res["decision"], "REJECT")
        self.assertTrue(any(r.startswith("det:") for r in res["reasons"]))

    def test_live_rewrite_mock(self):
        out = core.live_rewrite(PROBLEM, "plain", {"provider": "mock", "model": "mock"})
        self.assertEqual(out["status"], "NO_REWRITE_NEEDED")
        self.assertEqual(out["adapted_problem"], PROBLEM)
        self.assertEqual(out["returned_model"], "mock")
        self.assertIn(out["usd"], (0.0, None))

    def test_deterministic_rewrite_is_lossless_split(self):
        out = core.deterministic_rewrite(PROBLEM)
        self.assertIn("Question:", out)
        self.assertEqual(core.live_check(PROBLEM, out, "chunked")["decision"], "PASS")

    def test_app_imports_without_streamlit_server(self):
        self.assertTrue(callable(core.load_run))
        ast.parse((ROOT / "demo" / "app.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
