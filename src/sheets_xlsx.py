"""Excel versions of the annotation sheets: dropdowns, a one-click "ALL CLEAR", a live done/missing column, and an
Instructions tab. Labels go back to CSV with validation, so every downstream script (calibrate, adjudicate,
evaluate) keeps reading CSV.

  python src/sheets_xlsx.py export data/calibration/pilot/sheet_A.csv        # -> sheet_A.xlsx next to it
  python src/sheets_xlsx.py import data/calibration/pilot/sheet_A.xlsx       # -> sheet_A.csv (validated)
  python src/sheets_xlsx.py import <xlsx> --partial                          # write what is done so far
  make sheets-xlsx ANN=data/calibration/pilot      /   make import-sheets ANN=data/calibration/pilot

Works in Excel, Google Sheets (File > Import keeps the dropdowns) and LibreOffice. Annotators never see model names,
verifier decisions or whether an item is a repair; the xlsx carries exactly the columns of the CSV sheet.

QUICK = "ALL CLEAR" means: math PASS, target PASS, solvability NO, ambiguity NONE, leakage 0 / NONE. It fills only
the cells you left blank; anything you type wins. You still choose `presentation` (or `abstention_appropriate`
for a model that answered NO_REWRITE_NEEDED). ALL CLEAR together with a FAIL, NEW or leakage > 0 is an error.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ENUMS = {
    "adaptation_needed": ["YES", "NO", "UNCLEAR"],
    "math_fidelity": ["PASS", "FAIL", "UNSURE"],
    "target_preserved": ["PASS", "FAIL", "UNSURE"],
    "solvability_changed": ["NO", "YES", "UNSURE"],
    "ambiguity": ["NONE", "NEW", "RESOLVED"],
    "leakage_level": ["0", "1", "2", "3"],
    "leakage_type": ["NONE", "STRUCTURE", "STEPS", "OPERATION", "RELEVANCE", "INTERMEDIATE", "ANSWER"],
    "presentation": ["0", "1", "2", "3"],
    "abstention_appropriate": ["YES", "NO", "NA"],
    "confidence": ["HIGH", "MEDIUM", "LOW"],
}
FAILURE_CODES = {
    "QTY_CHANGE": "a number changed", "QTY_OMIT": "a number missing", "QTY_ADD": "a new number added",
    "UNIT_CHANGE": "a unit changed", "ENTITY_CHANGE": "a quantity now belongs to someone/something else",
    "REL_CHANGE": "a relation changed (e.g. 3 times -> 3 more; direction flipped)",
    "COND_OMIT": "a condition dropped", "COND_ADD": "a condition added",
    "QUANTIFIER_CHANGE": "each/all/some/remaining/at least changed", "ORDER_CHANGE": "time order changed",
    "TARGET_CHANGE": "asks for something else", "SOLVABILITY_CHANGE": "unsolvable or a different answer now",
    "CONTRADICTION": "the text contradicts itself", "AMBIGUITY_NEW": "a new second reading",
    "FALSE_DISAMBIGUATION": "picked a reading that does not match the intended one",
    "DISAMBIGUATION": "picked one reading of an ambiguous original (note which)",
    "LEAK_ANSWER": "states the answer", "LEAK_INTERMEDIATE": "states an intermediate value (also as a range/heading)",
    "LEAK_OPERATION": "names an operation not in the original", "LEAK_STEPS": "a plan or steps to follow",
    "LEAK_RELEVANCE": "says which facts matter or don't", "LEAK_STRUCTURE": "layout/labels mirror the solution order",
    "NO_ADAPT": "near-copy, nothing really changed", "OVER_EDIT": "changed far more than needed",
    "HARMFUL_FRAGMENT": "sentence fragments that hurt reading", "ENTITY_GROUPING": "facts regrouped confusingly",
    "FORMAT_FAIL": "the requested format not followed", "EXTRA_TEXT": "preamble or teacher note around the problem",
}
KEY = ["math_fidelity", "target_preserved", "solvability_changed", "ambiguity", "leakage_level"]
ALL_CLEAR = {"math_fidelity": "PASS", "target_preserved": "PASS", "solvability_changed": "NO", "ambiguity": "NONE",
             "leakage_level": "0", "leakage_type": "NONE"}
SHOWN = ["annotation_id", "transformation_requested", "model_status", "original", "adaptation"]
ORDER = ["quick", "math_fidelity", "target_preserved", "solvability_changed", "ambiguity", "leakage_level",
         "leakage_type", "presentation", "abstention_appropriate", "adaptation_needed", "failure_codes", "evidence",
         "confidence", "notes"]
HEADERS = {"transformation_requested": "requested", "model_status": "model said", "original": "ORIGINAL",
           "adaptation": "ADAPTATION (what the student would see)", "quick": "QUICK"}

INSTRUCTIONS = [
    ("SafeAdapt-Math labelling sheet", ""),
    ("Goal", "Is the ADAPTATION still exactly the same task as the ORIGINAL, unassisted? Easier to read is fine; "
             "easier to SOLVE is not."),
    ("Time", "About 1.5 minutes per row. Work top to bottom; take a break every 40 rows."),
    ("Rules", "Label blind: do not look up which model wrote it, do not open KEY_DO_NOT_OPEN.csv, do not discuss "
              "items with the other annotator until both of you are done."),
    ("Fast path", "Nothing wrong? Pick QUICK = ALL CLEAR, then choose presentation (0-3). That is two clicks. The "
                  "'done' column turns green when the row is complete."),
    ("Step 1 · Math", "Tick off every number, unit, owner, relation (and its direction), each/all/remaining/at least, "
                      "conditions, time order, and the question. Anything changed, missing or added -> "
                      "math_fidelity FAIL. Same question and unit -> target_preserved PASS."),
    ("Step 2 · Leakage", "Does it give away anything the student had to work out? 0 nothing; 1 layout/labels in "
                         "solution order (Step 1/Step 2...); 2 names an operation, a plan, an equation, or says which "
                         "facts matter; 3 states an intermediate value or the answer (also as a range like 'Stories "
                         "11 to 20'). Pick the most severe level and its type."),
    ("Step 3 · Presentation", "0 harder to read; 1 near-copy or broken fragments; 2 clearly easier; 3 much easier. If "
                              "'model said' is NO_REWRITE_NEEDED: leave presentation blank and set "
                              "abstention_appropriate (YES if the original was already short and clear)."),
    ("Other columns", "solvability_changed YES if it became unsolvable or has a different answer. ambiguity NEW if "
                      "it now allows a second reading; RESOLVED if it picked one reading of an ambiguous original "
                      "(say which in notes). adaptation_needed: judged on the ORIGINAL only."),
    ("Evidence", "For any FAIL, YES (solvability), NEW, or leakage > 0: paste the exact words in 'evidence' and add "
                 "failure codes (comma-separated; see the Codes tab)."),
    ("Unsure?", "Use UNSURE and write why in notes. Do not guess. Set confidence LOW."),
    ("Realistic prompt rows", "Label EVERYTHING in the adaptation, including 'Here is a simpler version' preambles "
                              "and tips: a teacher may paste the whole reply. Teacher-only notes: code EXTRA_TEXT."),
    ("When done", "Save. Then run: make import-sheets ANN=<this folder>  (it checks every row and lists problems)."),
    ("Full rubric", "docs/annotation_guide.md and docs/LABELLING_GUIDE.md"),
]


def _col(i: int) -> str:
    from openpyxl.utils import get_column_letter
    return get_column_letter(i)


def export(csv_path: Path, xlsx_path: Path | None = None, force: bool = False) -> Path:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    xlsx_path = xlsx_path or csv_path.with_suffix(".xlsx")
    if xlsx_path.exists() and not force:
        raise SystemExit(f"{xlsx_path} exists (it may hold labels); use --force to overwrite")
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    wb = Workbook()
    ws = wb.active
    ws.title = "Label"
    cols = ["#"] + SHOWN + ORDER + ["done"]
    ws.append([HEADERS.get(c, c) for c in cols])
    idx = {c: i + 1 for i, c in enumerate(cols)}
    for n, r in enumerate(rows, start=2):
        ws.append([n - 1] + [r.get(c, "") for c in SHOWN] + [r.get(c, "") if c != "quick" else "" for c in ORDER] + [""])
        L = {c: f"${_col(idx[c])}{n}" for c in cols}
        key_ok = "COUNTA(" + ",".join(L[c] for c in KEY) + ")=5"
        pres_ok = (f'OR({L["presentation"]}<>"",AND({L["model_status"]}="NO_REWRITE_NEEDED",'
                   f'{L["abstention_appropriate"]}<>""))')
        ws.cell(n, idx["done"], f'=IF(AND(OR({L["quick"]}="ALL CLEAR",{key_ok}),{pres_ok}),"done",'
                                f'IF(OR({L["quick"]}="ALL CLEAR",{key_ok}),"needs presentation",""))')
        lines = max(len(r.get("original", "")), len(r.get("adaptation", ""))) / 55 + r.get("adaptation", "").count("\n")
        ws.row_dimensions[n].height = min(330, max(30, 15 * (lines + 1)))
    widths = {"#": 5, "annotation_id": 12, "transformation_requested": 10, "model_status": 14, "original": 55,
              "adaptation": 55, "quick": 12, "evidence": 30, "notes": 30, "failure_codes": 22, "done": 18}
    head_fill = PatternFill("solid", fgColor="1F3A5F")
    label_fill = PatternFill("solid", fgColor="FFF4D6")
    for c, i in idx.items():
        ws.column_dimensions[_col(i)].width = widths.get(c, 14)
        h = ws.cell(1, i)
        h.font, h.fill = Font(bold=True, color="FFFFFF"), head_fill
        h.alignment = Alignment(wrap_text=True, vertical="center")
        for n in range(2, len(rows) + 2):
            cell = ws.cell(n, i)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if c in ORDER:
                cell.fill = label_fill
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = ws.cell(2, idx["quick"])
    last = len(rows) + 1
    for c, vals in {**ENUMS, "quick": ["ALL CLEAR"]}.items():
        dv = DataValidation(type="list", formula1='"' + ",".join(vals) + '"', allow_blank=True,
                            showErrorMessage=True, errorTitle="Not a valid label", error="Pick from the list")
        ws.add_data_validation(dv)
        dv.add(f"{_col(idx[c])}2:{_col(idx[c])}{last}")
    ws.conditional_formatting.add(f"A2:{_col(idx['done'])}{last}", FormulaRule(
        formula=[f'${_col(idx["done"])}2="done"'], fill=PatternFill("solid", fgColor="DDF2E3")))
    ws.auto_filter.ref = f"A1:{_col(idx['done'])}{last}"

    ins = wb.create_sheet("Instructions", 0)
    for k, v in INSTRUCTIONS:
        ins.append([k, v])
    ins.column_dimensions["A"].width, ins.column_dimensions["B"].width = 22, 110
    ins["A1"].font = Font(bold=True, size=14)
    ins.merge_cells("A1:B1")
    for row in ins.iter_rows(min_row=2):
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        row[0].alignment = Alignment(vertical="top")
    codes = wb.create_sheet("Codes")
    codes.append(["failure code", "meaning"])
    for k, v in FAILURE_CODES.items():
        codes.append([k, v])
    codes.column_dimensions["A"].width, codes.column_dimensions["B"].width = 22, 70
    codes["A1"].font = codes["B1"].font = Font(bold=True)
    wb.active = 1
    wb.save(xlsx_path)
    return xlsx_path


def _norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def validate(r: dict) -> tuple[dict, list[str], bool]:
    """Apply QUICK, normalise, and return (row, problems, complete)."""
    r = {k: _norm(v) for k, v in r.items()}
    quick = r.pop("quick", "").upper()
    probs = []
    if quick == "ALL CLEAR":
        for k, v in ALL_CLEAR.items():
            r[k] = r.get(k) or v
        if (r["math_fidelity"] in ("FAIL", "UNSURE") or r["target_preserved"] in ("FAIL", "UNSURE")
                or r["solvability_changed"] in ("YES", "UNSURE") or r["ambiguity"] == "NEW"
                or r["leakage_level"] not in ("", "0")):
            probs.append("QUICK=ALL CLEAR but a problem label is set; clear one of them")
    elif quick:
        probs.append(f"QUICK must be blank or ALL CLEAR, not {quick!r}")
    elif (r.get("model_status") == "NO_REWRITE_NEEDED" and not any(r.get(k) for k in KEY)
          and " ".join(r.get("original", "").split()) == " ".join(r.get("adaptation", "").split())):
        # an unchanged copy of the original is, by construction, the same task with nothing leaked
        for k, v in ALL_CLEAR.items():
            r[k] = v
        r["failure_codes"] = r.get("failure_codes", "")
    for k, vals in ENUMS.items():
        if r.get(k) and r[k].upper() not in vals:
            probs.append(f"{k}={r[k]!r} not in {vals}")
        elif r.get(k):
            r[k] = r[k].upper()
    codes = [c.strip().upper() for c in r.get("failure_codes", "").replace(";", ",").split(",") if c.strip()]
    bad = [c for c in codes if c not in FAILURE_CODES]
    if bad:
        probs.append(f"unknown failure code(s) {bad}; see the Codes tab")
    r["failure_codes"] = ",".join(codes)
    if r.get("leakage_level") == "0" and not r.get("leakage_type"):
        r["leakage_type"] = "NONE"
    if r.get("leakage_level") not in ("", "0") and r.get("leakage_type") in ("", "NONE"):
        probs.append("leakage_level > 0 needs a leakage_type")
    flagged = (r.get("math_fidelity") == "FAIL" or r.get("target_preserved") == "FAIL"
               or r.get("solvability_changed") == "YES" or r.get("ambiguity") == "NEW"
               or r.get("leakage_level") not in ("", "0"))
    if flagged and not r.get("evidence"):
        probs.append("a FAIL / YES / NEW / leakage label needs the exact words in evidence")
    abstained = r.get("model_status") == "NO_REWRITE_NEEDED"
    if abstained and not r.get("abstention_appropriate"):
        probs.append("model said NO_REWRITE_NEEDED: set abstention_appropriate")
    if not abstained:
        r["abstention_appropriate"] = r.get("abstention_appropriate") or "NA"
    complete = all(r.get(k) for k in KEY) and (bool(r.get("presentation")) or abstained) and not probs
    if not all(r.get(k) for k in KEY):
        probs.append("missing: " + ", ".join(k for k in KEY if not r.get(k)))
    elif not r.get("presentation") and not abstained:
        probs.append("missing: presentation")
    return r, probs, complete


def import_xlsx(xlsx_path: Path, csv_path: Path | None = None, partial: bool = False) -> tuple[int, list[str]]:
    from openpyxl import load_workbook
    from make_annotation_sheets import LABEL_COLUMNS

    csv_path = csv_path or xlsx_path.with_suffix(".csv")
    ws = load_workbook(xlsx_path, data_only=False)["Label"]
    header = [c.value for c in ws[1]]
    inv = {v: k for k, v in HEADERS.items()}
    names = [inv.get(h, h) for h in header]
    out, problems = [], []
    for n, cells in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        raw = {k: v for k, v in zip(names, cells) if k not in ("#", "done")}
        if not raw.get("annotation_id"):
            continue
        r, probs, complete = validate(raw)
        touched = any(_norm(raw.get(k)) for k in ORDER)
        if probs and (touched or not partial):
            problems += [f"row {n} ({r['annotation_id']}): {p}" for p in probs]
        out.append(r)  # incomplete rows keep what was entered; adjudicate/calibrate report them as unfinished
    cols = SHOWN + LABEL_COLUMNS
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in cols} for r in out)
    done = sum(1 for r in out if all(r.get(k) for k in KEY))
    return done, problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("csv", nargs="+")
    e.add_argument("--force", action="store_true")
    i = sub.add_parser("import")
    i.add_argument("xlsx", nargs="+")
    i.add_argument("--partial", action="store_true", help="keep incomplete rows as they are (progress check)")
    args = ap.parse_args()
    if args.cmd == "export":
        for p in args.csv:
            print("wrote", export(Path(p), force=args.force))
        return
    bad = False
    for p in args.xlsx:
        done, problems = import_xlsx(Path(p), partial=args.partial)
        print(f"{p}: {done} rows labelled -> {Path(p).with_suffix('.csv')}")
        for msg in problems[:200]:
            print("  FIX", msg)
        if len(problems) > 200:
            print(f"  ... and {len(problems) - 200} more")
        bad |= bool(problems)
    sys.exit(1 if bad and not args.partial else 0)


if __name__ == "__main__":
    main()
