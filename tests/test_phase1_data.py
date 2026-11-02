"""Run: python -m unittest discover -s tests -v   (from the repo root; all offline)

Phase 1 data tooling: pilot calibration sheets (src/calibrate.py) and the GSM-IC
sampler (src/fetch_data.py). The synthetic rows here are fixtures, not data.
"""
import csv
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calibrate import (PRELIMINARY, SHEET_COLUMNS, annotation_id, compare_to_preliminary, disagreements,  # noqa: E402
                       make_calibration_sheets, pilot_as_generations)
from common import read_jsonl  # noqa: E402
from fetch_data import sample_gsmic  # noqa: E402

PILOT_MODELS = {"claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"}
REQUIRED = {"generator", "transformation", "partition", "run_id", "status", "adapted_problem", "output_id", "source_id"}


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in columns} for r in rows)


class PilotCalibration(unittest.TestCase):
    def test_pilot_as_generations_schema(self):
        gens = pilot_as_generations(read_jsonl(ROOT / "pilot" / "pilot_outputs.jsonl"))
        self.assertEqual(len(gens), 70)
        for g in gens:
            self.assertTrue(REQUIRED <= set(g), REQUIRED - set(g))
            self.assertEqual(g["partition"], "dev")
            self.assertEqual(g["run_id"], "pilot")
        self.assertEqual({g["generator"] for g in gens}, PILOT_MODELS)

    def test_calibration_sheets_blind_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_calibration_sheets(Path(tmp), seed=2880)
            sheets = {n: read_csv(Path(tmp) / n) for n in ("sheet_A.csv", "sheet_B.csv")}
            key = read_csv(Path(tmp) / "KEY_DO_NOT_OPEN.csv")
        a, b = sheets["sheet_A.csv"], sheets["sheet_B.csv"]
        self.assertEqual(len(a), 70)
        self.assertEqual(len(b), 70)
        self.assertEqual(len(key), 70)
        self.assertEqual({r["annotation_id"] for r in a}, {r["annotation_id"] for r in b})
        self.assertEqual({r["annotation_id"] for r in a}, {r["annotation_id"] for r in key})
        self.assertEqual(list(a[0]), SHEET_COLUMNS)
        for r in a + b:
            for c in ("adaptation", "original", "model_status", "transformation_requested", "annotation_id"):
                for m in PILOT_MODELS | {"haiku", "opus", "sonnet"}:
                    self.assertNotIn(m, r[c].lower(), f"model name leaked in {c}")
            self.assertTrue(r["annotation_id"].startswith("a"))
        for r in key:  # same blinding rule as make_annotation_sheets
            self.assertEqual(r["annotation_id"], annotation_id(r["output_id"], 2880))
            self.assertEqual(r["double_annotated"], "True")

    def test_disagreement_list(self):
        items = [{"annotation_id": f"a{i}", "original": f"orig {i}", "adaptation": f"adapt {i}", "math_fidelity": "PASS",
                  "target_preserved": "PASS", "solvability_changed": "NO", "ambiguity": "NONE", "leakage_level": "0",
                  "presentation": "2", "evidence": f"ev{i}"} for i in range(3)]
        b_items = [dict(r) for r in items]
        b_items[0]["math_fidelity"] = "FAIL"
        b_items[0]["evidence"] = "quantity dropped"
        b_items[2]["leakage_level"] = "2"
        key_rows = [{"annotation_id": f"a{i}", "output_id": f"o{i}", "source_id": f"s{i}", "generator": "g",
                     "transformation": "plain", "partition": "dev"} for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_csv(tmp / "A.csv", SHEET_COLUMNS, items)
            write_csv(tmp / "B.csv", SHEET_COLUMNS, b_items)
            write_csv(tmp / "KEY.csv", list(key_rows[0]), key_rows)
            df = disagreements(tmp / "A.csv", tmp / "B.csv", tmp / "KEY.csv")
            self.assertTrue((tmp / "disagreements.csv").exists())
        self.assertEqual(len(df), 2)
        self.assertEqual(df["label"].tolist(), ["leakage_level", "math_fidelity"])  # sorted by label
        row = df[df["label"] == "math_fidelity"].iloc[0]
        self.assertEqual((row["A"], row["B"], row["evidence_B"], row["output_id"], row["original"]),
                         ("PASS", "FAIL", "quantity dropped", "o0", "orig 0"))

    def test_compare_preliminary_identity(self):
        """Adjudicated labels copied from the preliminary file must agree with it perfectly."""
        pre = read_csv(PRELIMINARY)
        key_rows = [{"annotation_id": annotation_id(r["output_id"], 2880), "output_id": r["output_id"]} for r in pre]
        adj = [{"annotation_id": k["annotation_id"], **r} for k, r in zip(key_rows, pre)]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_csv(tmp / "ADJ.csv", ["annotation_id", *pre[0].keys()], adj)
            write_csv(tmp / "KEY.csv", ["annotation_id", "output_id"], key_rows)
            table = compare_to_preliminary(tmp / "ADJ.csv", tmp / "KEY.csv")
        self.assertIn("SAFE", table["label"].tolist())
        n = dict(zip(table["label"], table["n"]))
        self.assertEqual((n["math_fidelity"], n["leakage_level"], n["SAFE"]), (70, 70, 70))
        self.assertLess(n["presentation"], 70)  # blank for NO_REWRITE_NEEDED outputs, so excluded
        for _, r in table.iterrows():
            self.assertGreater(r["n"], 0, r["label"])
            self.assertAlmostEqual(r["raw_agreement"], 1.0, msg=r["label"])
            self.assertAlmostEqual(r["kappa"], 1.0, msg=r["label"])


class GsmicSampler(unittest.TestCase):
    @staticmethod
    def fixture(per_stratum: int = 5) -> list[dict]:
        rows, i = [], 0
        for role in ("overlapped", "nonoverlapped"):
            for num in ("in_range", "out_range"):
                for sent in ("in_topic", "out_topic"):
                    for _ in range(per_stratum):
                        rows.append({"split": "2step", "row": i, "original_question": f"Q{i}: Ann has {i} pens. How many?",
                                     "new_question": f"Q{i}: Ann has {i} pens. Bob has 3 cats. How many?", "answer": str(i),
                                     "n_steps": 2, "role": "Bob", "number": "3", "sentence_template": "{role} has {number} cats.",
                                     "role_label": role, "number_label": num, "sentence_label": sent})
                        i += 1
        return rows

    def test_gsmic_sampler_fixture(self):
        rows = self.fixture()
        out = sample_gsmic(rows, n=12, seed=2880)
        self.assertEqual(len(out), 12)
        self.assertEqual(out, sample_gsmic(rows, n=12, seed=2880))
        self.assertNotEqual([r["source_id"] for r in out], [r["source_id"] for r in sample_gsmic(rows, n=12, seed=1)])
        counts = Counter((r["role_label"], r["number_label"], r["sentence_label"]) for r in out)
        self.assertEqual(len(counts), 8)  # every stratum represented
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        self.assertEqual(len({r["original_text"] for r in out}), 12)
        r = out[0]
        self.assertEqual(r["partition"], "ext_gsmic")
        self.assertEqual(r["dataset"], "gsmic")
        self.assertEqual(r["source_id"], f"gsmic-2step-{r['row']}")
        self.assertEqual(r["distractor"], "Bob has 3 cats.")
        self.assertIn(r["distractor"], r["text"])
        self.assertEqual(set(r["tags"]), {"percent", "fraction", "comparison", "money", "time", "measure", "conditional"})
        self.assertEqual(len(r["source_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
