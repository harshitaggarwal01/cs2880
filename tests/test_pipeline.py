"""Run: python -m unittest discover -s tests -v   (from the repo root)

The stress cases are CONSTRUCTED examples for software testing. They are not
measured model failures and must never be reported as such.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseline import is_lossless, render  # noqa: E402
from common import read_jsonl  # noqa: E402
from deterministic_checks import check, derived_values, numbers  # noqa: E402
from evaluate import cohen_kappa, gwet_ac1, holm, mcnemar_exact  # noqa: E402
from verify import decide, program_check, safe_eval  # noqa: E402


class DeterministicChecks(unittest.TestCase):
    def test_stress_cases(self):
        for case in read_jsonl(ROOT / "tests" / "stress_cases.jsonl"):
            with self.subTest(case=case["case"]):
                self.assertEqual(check(case["source"], case["candidate"])["decision"], case["expect"])

    def test_number_words_and_fractions(self):
        self.assertIn(3, numbers("three boxes"))
        self.assertIn(0.25, [float(v) for v in numbers("1/4 times more")])
        self.assertIn(0.2, [float(v) for v in numbers("20% tax")])

    def test_derived_values_cover_products(self):
        self.assertIn(120, derived_values(numbers("15 tickets in each of 8 rows")))

    def test_identity_passes(self):
        s = "Lisa has 18 more dresses than Ana. If the number of their dresses combined is 48, how many dresses does Ana have?"
        self.assertEqual(check(s, s)["decision"], "PASS")


class Baseline(unittest.TestCase):
    def test_lossless_on_all_frozen_sources(self):
        for f in ("dev.jsonl", "main.jsonl", "ext_asdiv.jsonl"):
            for r in read_jsonl(ROOT / "data" / "frozen" / f):
                with self.subTest(source=r["source_id"]):
                    self.assertTrue(is_lossless(r["text"], render(r["text"])))

    def test_baseline_never_flagged_reject(self):
        for r in read_jsonl(ROOT / "data" / "frozen" / "main.jsonl"):
            self.assertNotEqual(check(r["text"], render(r["text"]), "chunked")["decision"], "REJECT", r["source_id"])


class ProgramLayer(unittest.TestCase):
    def test_safe_eval(self):
        self.assertEqual(safe_eval("24 + 2*24 - 6"), 66)
        self.assertEqual(safe_eval("20*(1+1/4)*30"), 750)
        self.assertIsNone(safe_eval("__import__('os').system('echo hi')"))
        self.assertIsNone(safe_eval("9**999999"))

    def test_program_mismatch_rejects(self):
        prog = program_check({"program": "24+2*24-6"}, {"program": "24+2*24"})
        self.assertEqual(prog["status"], "MISMATCH")
        det = {"decision": "PASS", "flags": []}
        critic = {"overall": "SAFE", "failure_codes": []}
        self.assertEqual(decide(det, critic, prog)[0], "REJECT")
        self.assertEqual(decide(det, critic, {"status": "MATCH", "relation_types_equal": True})[0], "PASS")
        self.assertEqual(decide(det, None, None)[0], "REVIEW")


class Stats(unittest.TestCase):
    def test_mcnemar(self):
        self.assertAlmostEqual(mcnemar_exact([1] * 10, [0] * 10)[2], 2 / 2 ** 10)
        self.assertEqual(mcnemar_exact([1, 0], [1, 0])[2], 1.0)

    def test_holm_monotone(self):
        self.assertEqual(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])

    def test_agreement(self):
        a = ["PASS"] * 18 + ["FAIL"] * 2
        self.assertAlmostEqual(cohen_kappa(a, a), 1.0)
        self.assertAlmostEqual(gwet_ac1(a, a), 1.0)
        self.assertLess(cohen_kappa(a, list(reversed(a))), 0.0)


class MockEndToEnd(unittest.TestCase):
    """Offline run of generate -> verify -> repair -> annotation sheets with the mock provider."""

    def test_mock_pipeline(self):
        run = lambda *a: subprocess.run([sys.executable, *a], cwd=ROOT, check=True, capture_output=True, text=True)  # noqa: E731
        out_dir = ROOT / "data" / "outputs" / "main-v1-mock"
        for p in out_dir.glob("*.jsonl"):
            p.unlink()
        run("src/collect_outputs.py", "--config", "config.example.yaml", "--pilot", "--mock")
        gens = out_dir / "pilot_generations.jsonl"
        self.assertEqual(len(read_jsonl(gens)), 10 * 2 * 2)
        run("src/verify.py", str(gens), "--config", "config.example.yaml", "--mock")
        ver = next(out_dir.glob("pilot_generations.verify-*.jsonl"))
        decisions = {r["decision"] for r in read_jsonl(ver)}
        self.assertTrue(decisions <= {"PASS", "REVIEW", "REJECT"})
        run("src/repair.py", str(gens), str(ver), "--config", "config.example.yaml", "--mock")
        run("src/make_annotation_sheets.py", str(gens))
        key = ROOT / "data" / "annotations" / "main-v1-mock" / "KEY_DO_NOT_OPEN.csv"
        self.assertTrue(key.exists())


if __name__ == "__main__":
    unittest.main()
