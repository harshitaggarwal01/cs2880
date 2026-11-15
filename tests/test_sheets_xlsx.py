"""Run: python -m unittest tests.test_sheets_xlsx -v   (offline)"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import sheets_xlsx  # noqa: E402
from make_annotation_sheets import LABEL_COLUMNS  # noqa: E402


def write_csv(path, n=4, status=""):
    cols = sheets_xlsx.SHOWN + LABEL_COLUMNS
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i in range(n):
            w.writerow({c: "" for c in cols} | {"annotation_id": f"a{i}", "transformation_requested": "plain",
                                                 "model_status": status, "original": "Tom has 3 apples.",
                                                 "adaptation": "Tom has 3 apples."})


class RoundTrip(unittest.TestCase):
    def test_export_has_tabs_dropdowns_and_import_validates(self):
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "sheet_A.csv"
            write_csv(c)
            x = sheets_xlsx.export(c)
            wb = load_workbook(x)
            self.assertEqual(wb.sheetnames, ["Instructions", "Label", "Codes"])
            ws = wb["Label"]
            self.assertGreaterEqual(len(ws.data_validations.dataValidation), len(sheets_xlsx.ENUMS))
            col = {c.value: i + 1 for i, c in enumerate(ws[1])}
            ws.cell(2, col["QUICK"], "ALL CLEAR"); ws.cell(2, col["presentation"], 3)
            ws.cell(3, col["QUICK"], "ALL CLEAR"); ws.cell(3, col["leakage_level"], 2)
            for k, v in {"math_fidelity": "fail", "target_preserved": "PASS", "solvability_changed": "NO",
                         "ambiguity": "NONE", "leakage_level": 0, "presentation": 1,
                         "evidence": "5% is deducted", "failure_codes": "qty_change; bogus"}.items():
                ws.cell(4, col[k], v)
            wb.save(x)
            done, probs = sheets_xlsx.import_xlsx(x, partial=True)
            rows = list(csv.DictReader(open(c)))
            self.assertEqual(rows[0]["math_fidelity"], "PASS")
            self.assertEqual(rows[0]["leakage_type"], "NONE")
            self.assertEqual(rows[0]["abstention_appropriate"], "NA")
            self.assertEqual(rows[2]["math_fidelity"], "FAIL")              # normalised to upper case
            self.assertTrue(any("row 3" in p and "ALL CLEAR" in p for p in probs))
            self.assertTrue(any("row 4" in p and "BOGUS" in p for p in probs))
            self.assertFalse(any("row 2" in p for p in probs))
            self.assertFalse(any("row 5" in p for p in probs))               # untouched rows are fine in --partial

    def test_abstention_rows_need_abstention_not_presentation(self):
        r, probs, complete = sheets_xlsx.validate({"annotation_id": "x", "model_status": "NO_REWRITE_NEEDED",
                                                   "quick": "ALL CLEAR"})
        self.assertFalse(complete)
        self.assertTrue(any("abstention_appropriate" in p for p in probs))
        r, probs, complete = sheets_xlsx.validate({"annotation_id": "x", "model_status": "NO_REWRITE_NEEDED",
                                                   "quick": "ALL CLEAR", "abstention_appropriate": "yes"})
        self.assertTrue(complete, probs)

    def test_export_refuses_to_overwrite_labels(self):
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "s.csv"
            write_csv(c)
            sheets_xlsx.export(c)
            with self.assertRaises(SystemExit):
                sheets_xlsx.export(c)


if __name__ == "__main__":
    unittest.main()
