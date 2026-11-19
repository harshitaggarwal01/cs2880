"""adjudicate.py: abstention rows need no presentation label, and step 2 never counts an item twice."""
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from adjudicate import apply_resolved, merge  # noqa: E402
from make_annotation_sheets import LABEL_COLUMNS  # noqa: E402

META = {"transformation_requested": "plain", "original": "o", "adaptation": "o"}
SAFE = {"math_fidelity": "PASS", "target_preserved": "PASS", "solvability_changed": "NO", "ambiguity": "NONE",
        "leakage_level": "0"}


def sheet(rows):
    out = []
    for aid, status, pres in rows:
        r = {c: "" for c in LABEL_COLUMNS}
        r.update(SAFE, presentation=pres)
        out.append({"annotation_id": aid, "model_status": status, **META, **r})
    return pd.DataFrame(out)


class TestAbstention(unittest.TestCase):
    def test_blank_presentation_ok_for_abstention_only(self):
        with tempfile.TemporaryDirectory() as d:
            a = sheet([("x1", "NO_REWRITE_NEEDED", ""), ("x2", "REWRITTEN", "")])
            a.to_csv(Path(d, "A.csv"), index=False)
            a.to_csv(Path(d, "B.csv"), index=False)
            final, todo, _ = merge(Path(d, "A.csv"), Path(d, "B.csv"))
        self.assertEqual(list(final["annotation_id"]), ["x1"])     # abstention: agreed without presentation
        self.assertEqual(list(todo["annotation_id"]), ["x2"])      # a rewrite still needs presentation

    def test_resolved_row_already_final_is_not_duplicated(self):
        final = pd.DataFrame([{"annotation_id": "x1", "source": "agreed"}])
        resolved = pd.DataFrame([{"annotation_id": "x1", "model_status": "NO_REWRITE_NEEDED", **META,
                                  **{f"{c}_final": SAFE.get(c, "") for c in LABEL_COLUMNS}}])
        out, _ = apply_resolved(final, resolved)
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
