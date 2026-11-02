"""Run: python -m unittest tests.test_redteam -v   (from the repo root). Mock provider only; no API calls."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from common import FROZEN, read_jsonl  # noqa: E402
from llm import load_prompt  # noqa: E402
from make_annotation_sheets import LABEL_COLUMNS  # noqa: E402
from llm import Provider  # noqa: E402
from redteam import GEN_FILE, attack, make_blind_sheet, recall_under_attack, run_attacks  # noqa: E402

CFG = {"run_id": "test-run", "generators": [{"name": "g1", "provider": "mock", "model": "mock"}]}


class ScriptedProvider(Provider):
    name = "scripted"

    def __init__(self, replies):
        super().__init__("scripted-model")
        self.replies, self.users = list(replies), []

    def _call(self, system, user, json_schema):
        self.users.append(user)
        return dict(raw_output=json.dumps(self.replies.pop(0)), usage={"input_tokens": 1, "output_tokens": 1})


class Redteam(unittest.TestCase):
    def test_attacker_prompt_has_sections(self):
        system, user, sha = load_prompt("attacker_v1")
        self.assertIn("{problem_text}", user)
        self.assertIn("adapted_problem", system)
        self.assertIn("tactic", system)
        self.assertEqual(len(sha), 64)

    def test_redteam_outputs_never_enter_main_sheets(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / CFG["run_id"]
            path = run_attacks(CFG, run_dir, n_sources=3, mock=True)
            self.assertEqual(path, run_dir / "redteam" / GEN_FILE)
            written = [p for p in run_dir.rglob("*") if p.is_file()]
            self.assertTrue(written)
            self.assertTrue(all((run_dir / "redteam") in p.parents for p in written))
            rows = read_jsonl(path)
            self.assertEqual(len(rows), 3)
            for r in rows:
                self.assertTrue(r["output_id"].startswith(f"{CFG['run_id']}|redteam"))
                self.assertEqual((r["transformation"], r["status"], r["prompt_version"]), ("redteam", "ATTACK", "attacker_v1"))
                self.assertEqual(r["generator"], "redteam:mock")
            run_attacks(CFG, run_dir, n_sources=3, mock=True)  # resume: nothing appended
            self.assertEqual(len(read_jsonl(path)), 3)

    def test_attack_feeds_back_flags_and_keeps_last(self):
        src = {"source_id": "s1", "dataset": "d", "partition": "main", "text": "Ann has 3 apples and buys 4 more. How many apples?"}
        bad = {"adapted_problem": "Ann has 3 apples. Add 4 apples. How many apples?", "tactic": "obvious"}
        good = {"adapted_problem": "Ann has 3 apples and gets 4 more. How many apples?", "tactic": "order"}
        p = ScriptedProvider([bad, good])
        rec = attack(src, p, rounds=3)
        self.assertEqual(rec["rounds_used"], 2)  # stops once no deterministic flag remains
        self.assertIn("caught for", p.users[1])
        self.assertEqual((rec["tactic"], rec["generator"], rec["usage"]["input_tokens"]), ("order", "redteam:scripted-model", 2))
        self.assertEqual(rec["adapted_problem"], good["adapted_problem"])

    def test_recall_under_attack_math(self):
        def row(i, det, dec):
            return {"output_id": f"o{i}", "decision": dec, "deterministic": {"decision": det}}
        rows = [row(0, "REJECT", "REJECT"), row(1, "PASS", "REVIEW"), row(2, "PASS", "PASS"), row(3, "REVIEW", "REVIEW")]
        gens = [{"output_id": f"o{i}", "tactic": t} for i, t in enumerate(["order", "order", "relabel", "relabel"])]
        res = recall_under_attack(rows, None, gens)
        self.assertEqual(res["n_attacks"], 4)
        self.assertAlmostEqual(res["det_flag_rate"], 0.5)
        self.assertAlmostEqual(res["full_flag_rate"], 0.75)
        self.assertAlmostEqual(res["full_reject_rate"], 0.25)
        self.assertAlmostEqual(res["by_tactic"]["order"]["full_flag_rate"], 1.0)
        self.assertAlmostEqual(res["by_tactic"]["relabel"]["det_flag_rate"], 0.5)
        labels = pd.DataFrame({"output_id": ["o0", "o1", "o2", "o3"], "leakage_level": [2, 1, 1, 0]})
        res = recall_under_attack(rows, labels)
        self.assertEqual(res["n_confirmed_unsafe"], 3)  # o0, o1, o2
        self.assertAlmostEqual(res["det_recall_confirmed"], 1 / 3)
        self.assertAlmostEqual(res["full_recall_confirmed"], 2 / 3)
        self.assertAlmostEqual(res["reject_recall_confirmed"], 1 / 3)
        self.assertNotIn("by_tactic", recall_under_attack(rows))

    def test_blind_sheet_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / CFG["run_id"]
            path = run_attacks(CFG, run_dir, n_sources=4, mock=True)
            sources = read_jsonl(FROZEN / "main.jsonl")[:4]
            with open(run_dir / "generations.jsonl", "w") as f:  # stand-in main generations file
                for s in sources:
                    f.write(json.dumps({"output_id": f"{CFG['run_id']}|g1|plain|{s['source_id']}", "generator": "g1",
                                        "transformation": "plain", "source_id": s["source_id"],
                                        "adapted_problem": s["text"], "status": "REWRITTEN"}) + "\n")
            out = make_blind_sheet(path, run_dir / "redteam" / "blind.csv", n=3, seed=2880)
            with open(out, newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0]), ["annotation_id", "transformation_requested", "model_status", "original",
                                             "adaptation", *LABEL_COLUMNS])
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(r["annotation_id"].startswith("a") and len(r["annotation_id"]) == 11 for r in rows))
            self.assertEqual({r["transformation_requested"] for r in rows}, {"plain"})
            key = pd.read_csv(out.with_name("blind_KEY_DO_NOT_OPEN.csv"))
            self.assertEqual(int(key["is_attack"].sum()), 3)
            with self.assertRaises(ValueError):
                make_blind_sheet(path, Path(tmp) / "elsewhere.csv")


if __name__ == "__main__":
    unittest.main()
