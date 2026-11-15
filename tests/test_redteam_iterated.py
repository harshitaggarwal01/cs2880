"""Run: python -m unittest tests.test_redteam_iterated -v   (offline; scripted/mock providers only)"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import read_jsonl  # noqa: E402
from llm import Provider  # noqa: E402
from redteam import ITER_FILE, SUBDIR, _assert_quarantined, iterated_summary, run_iterated, split_sources  # noqa: E402

CFG = {"run_id": "iter-test", "generators": [{"name": "g1", "provider": "mock", "model": "mock"}]}
SOURCES = [{"source_id": f"s{i}", "dataset": "d", "partition": "main", "text": f"Ann has {i + 2} apples and {i + 3} pears. How many fruits?"}
           for i in range(8)]
FEEDBACK, HELD = split_sources(SOURCES, 0.25)
HELD_TEXTS = {s["text"] for s in HELD}


class RoundProvider(Provider):
    """Round = call index // sources per round. Returns the source text tagged with the round."""
    name = "scripted"

    def __init__(self, per_round):
        super().__init__("scripted-model")
        self.per_round, self.calls, self.prompts = per_round, 0, []  # prompts: (round, user)

    def _call(self, system, user, json_schema):
        rnd = self.calls // self.per_round + 1
        self.calls += 1
        self.prompts.append((rnd, user))
        text = re.search(r"<<<\n(.*?)\n>>>", user, re.S).group(1)
        return dict(raw_output=json.dumps({"adapted_problem": f"{text} ZZ{rnd}", "tactic": f"t{rnd}"}),
                    usage={"input_tokens": 1, "output_tokens": 1})


def checker(source_text, cand):
    rnd = re.search(r"ZZ(\d+)", cand).group(1)
    code = "HELDCODE" if source_text in HELD_TEXTS else f"CODE{rnd}"
    # held-out attacks evade from round 2 on; feedback attacks are always flagged
    if source_text in HELD_TEXTS and int(rnd) >= 2:
        return {"decision": "PASS", "flags": []}
    return {"decision": "REVIEW", "flags": [{"code": code, "detail": f"d{rnd}"}]}


class Iterated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / CFG["run_id"]
        self.prov = RoundProvider(len(SOURCES))
        self.summary = run_iterated(CFG, self.run_dir, rounds=4, provider=self.prov, checker=checker,
                                    sources=SOURCES, heldout_frac=0.25)

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_disjoint_and_deterministic(self):
        self.assertFalse({s["source_id"] for s in FEEDBACK} & {s["source_id"] for s in HELD})
        self.assertEqual(len(FEEDBACK) + len(HELD), len(SOURCES))
        self.assertEqual((FEEDBACK, HELD), split_sources(SOURCES, 0.25))
        self.assertEqual(len(HELD), 2)

    def test_quarantine_holds_across_rounds(self):
        files = [p for p in self.run_dir.rglob("*") if p.is_file()]
        self.assertTrue(files)
        self.assertTrue(all((self.run_dir / SUBDIR) in p.parents for p in files))
        recs = read_jsonl(self.run_dir / SUBDIR / ITER_FILE)
        self.assertEqual(len(recs), 4 * len(SOURCES))
        self.assertEqual({r["round"] for r in recs}, {1, 2, 3, 4})
        for r in recs:
            self.assertTrue(r["output_id"].startswith(f"{CFG['run_id']}|{SUBDIR}"))
            self.assertEqual((r["transformation"], r["status"]), ("redteam", "ATTACK"))
        with self.assertRaises(ValueError):
            _assert_quarantined(Path(self.tmp.name) / "elsewhere.jsonl", self.run_dir)

    def test_round_k_attacker_sees_only_round_k_minus_1_verdicts(self):
        for rnd, user in self.prov.prompts:
            if rnd == 1:
                self.assertNotIn("CHECKER FEEDBACK", user)
                continue
            self.assertIn(f"FROM ROUND {rnd - 1}]", user)
            self.assertIn(f"CODE{rnd - 1}", user)
            for older in range(1, rnd - 1):
                self.assertNotIn(f"CODE{older}", user)
                self.assertNotIn(f"ROUND {older}]", user)
                self.assertNotIn(f"ZZ{older}", user)
            self.assertNotIn(f"ZZ{rnd}", user)  # nothing from the current round either

    def test_held_out_set_never_used_for_feedback(self):
        for rnd, user in self.prov.prompts:
            self.assertNotIn("HELDCODE", user)
            for t in HELD_TEXTS:
                self.assertNotIn(f"{t} ZZ", user)  # no held-out attempt text is ever echoed back
        recs = read_jsonl(self.run_dir / SUBDIR / ITER_FILE)
        held_prompts = [r["attacker_user_prompt"] for r in recs if r["split"] == "heldout" and r["round"] > 1]
        self.assertTrue(held_prompts)
        for u in held_prompts:  # held-out attacker input is the digest only: no per-item attempt
            self.assertIn("Checker verdicts on", u)
            self.assertNotIn("Your previous attempt", u)
        fb_prompts = [r["attacker_user_prompt"] for r in recs if r["split"] == "feedback" and r["round"] > 1]
        self.assertTrue(all("Your previous attempt" in u for u in fb_prompts))

    def test_summary_reports_held_out_recall_per_round(self):
        s = self.summary.set_index("round")
        self.assertEqual(list(s.index), [1, 2, 3, 4])
        self.assertEqual(s.loc[1, "heldout_n"], len(HELD))
        self.assertAlmostEqual(s.loc[1, "heldout_recall"], 1.0)
        self.assertAlmostEqual(s.loc[3, "heldout_recall"], 0.0)  # planted: held-out attacks evade after round 1
        self.assertAlmostEqual(s.loc[3, "feedback_recall"], 1.0)
        self.assertTrue((self.run_dir / SUBDIR / "redteam_iterated_summary.csv").exists())
        self.assertEqual(len(iterated_summary([])), 0)

    def test_resume_appends_nothing(self):
        n = len(read_jsonl(self.run_dir / SUBDIR / ITER_FILE))
        run_iterated(CFG, self.run_dir, rounds=4, provider=RoundProvider(len(SOURCES)), checker=checker,
                     sources=SOURCES, heldout_frac=0.25)
        self.assertEqual(len(read_jsonl(self.run_dir / SUBDIR / ITER_FILE)), n)

    def test_mock_provider_offline_on_frozen_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "mock-run"
            s = run_iterated({**CFG, "run_id": "mock-run"}, run_dir, n_sources=5, rounds=2, mock=True)
            self.assertEqual(list(s["round"]), [1, 2])
            self.assertTrue(all((run_dir / SUBDIR) in p.parents for p in run_dir.rglob("*") if p.is_file()))


if __name__ == "__main__":
    unittest.main()
