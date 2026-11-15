"""Run: python -m unittest discover -s tests -v   (offline; local fixtures only, no network)

Broader-scope adapters: MGSM and science samplers (src/fetch_data.py), the extra prompts, and src/prompt_vars.py.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import read_jsonl  # noqa: E402
from fetch_data import (MGSM_LICENSE, SCIENCE_LICENSE, sample_mgsm, sample_science, science_text)  # noqa: E402
from prompt_vars import ALLOWED_HELP, render_prompt  # noqa: E402

FROZEN_PARTITIONS = {"dev", "main", "ext_asdiv", "ext_gsm1k"}
MGSM_ROWS = [{"row": i, "question": f"Pregunta {i}: Ana tiene {i + 2} manzanas y compra 3 mas. Cuantas tiene?",
              "answer": str(i + 5)} for i in range(250)]
SCI_ROWS = [{"id": f"Fix_{i:03d}", "question": f"A car travels {i + 10} km in 2 hours. Which is true?" if i % 3 else "Which is a mammal?",
             "choices": {"text": ["one", "two", "three", "four"], "label": ["A", "B", "C", "D"]},
             "answerKey": "ABCD"[i % 4]} for i in range(60)]


class Mgsm(unittest.TestCase):
    def test_deterministic_and_seed_sensitive(self):
        a = sample_mgsm(MGSM_ROWS, n=12, seed=2880, lang="es")
        self.assertEqual(a, sample_mgsm(MGSM_ROWS, n=12, seed=2880, lang="es"))
        self.assertEqual(len(a), 12)
        self.assertNotEqual([r["row"] for r in a], [r["row"] for r in sample_mgsm(MGSM_ROWS, n=12, seed=1, lang="es")])

    def test_partition_and_parallel_languages(self):
        es = sample_mgsm(MGSM_ROWS, lang="es")
        fr = sample_mgsm(MGSM_ROWS, lang="fr")
        self.assertEqual({r["partition"] for r in es}, {"ext_mgsm_es"})
        self.assertEqual({r["partition"] for r in fr}, {"ext_mgsm_fr"})
        self.assertEqual([r["row"] for r in es], [r["row"] for r in fr])
        self.assertFalse({r["partition"] for r in es + fr} & FROZEN_PARTITIONS)
        self.assertTrue(all(r["source_id"].startswith("mgsm-") for r in es))
        self.assertTrue(all(r["lang"] == "es" and r["text"] and r["source_sha256"] for r in es))

    def test_licence_recorded(self):
        self.assertIn("CC BY-SA 4.0", MGSM_LICENSE)
        self.assertIn("CC BY-SA 4.0", SCIENCE_LICENSE)


class Science(unittest.TestCase):
    def test_deterministic_quantitative_only(self):
        a = sample_science(SCI_ROWS, n=12, seed=2880)
        self.assertEqual(a, sample_science(SCI_ROWS, n=12, seed=2880))
        self.assertEqual(len(a), 12)
        self.assertEqual(len({r["source_id"] for r in a}), 12)
        for r in a:
            self.assertRegex(r["text"], r"\d")
            self.assertIn("(A) ", r["text"])
        self.assertNotEqual([r["source_id"] for r in a], [r["source_id"] for r in sample_science(SCI_ROWS, n=12, seed=7)])

    def test_partition_separate(self):
        a = sample_science(SCI_ROWS)
        self.assertEqual({r["partition"] for r in a}, {"ext_science"})
        self.assertFalse({r["partition"] for r in a} & FROZEN_PARTITIONS)
        self.assertTrue(science_text(SCI_ROWS[1]).startswith("A car travels"))

    def test_frozen_files_untouched_by_adapters(self):
        for name in ("dev", "main", "ext_asdiv"):
            parts = {r["partition"] for r in read_jsonl(ROOT / "data" / "frozen" / f"{name}.jsonl")}
            self.assertEqual(parts, {name})


class Prompts(unittest.TestCase):
    def test_translate_prompt(self):
        system, user, sha = render_prompt("translate_plain_v1", problem_text="Ann has {2} apples.", target_language="Spanish")
        self.assertIn("Spanish", system)
        self.assertIn("Ann has {2} apples.", user)
        self.assertNotIn("{target_language}", system + user)
        self.assertNotIn("{problem_text}", user)
        self.assertEqual(len(sha), 64)
        self.assertIn('"adapted_problem"', system)  # JSON braces survive

    def test_hint_levels_prompt(self):
        for level in ALLOWED_HELP:
            system, user, _ = render_prompt("hint_levels_v1", problem_text="P", allowed_help=level)
            self.assertIn(f"allowed_help = {level}", system)
            self.assertNotIn("{allowed_help}", system + user)
            for lv in ("none", "cue", "worked_step"):
                self.assertIn(f"- {lv}:", system)

    def test_validation(self):
        with self.assertRaises(ValueError):
            render_prompt("hint_levels_v1", problem_text="P", allowed_help="solution")
        with self.assertRaises(ValueError):
            render_prompt("translate_plain_v1", problem_text="P")  # target_language missing

    def test_existing_prompts_unchanged_behaviour(self):
        system, user, _ = render_prompt("plain_v1", problem_text="Hello")
        self.assertIn("Hello", user)
        json.loads('{"a": 1}')


if __name__ == "__main__":
    unittest.main()
