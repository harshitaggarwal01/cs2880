"""Rubric calibration on the 70 dev-pilot outputs (both annotators label all of them blind).

  python src/calibrate.py --make-sheets [--out data/calibration/pilot] [--seed 2880]
  python src/calibrate.py --agreement A.csv B.csv              # agreement table (markdown)
  python src/calibrate.py --disagreements A.csv B.csv KEY.csv  # one row per (item, label) where A != B
  python src/calibrate.py --compare-preliminary ADJ.csv KEY.csv # human adjudicated vs AI preliminary labels

Unlike the main-study sheets (30% double annotation), sheet_A and sheet_B here
both hold every pilot item, shuffled and blinded with the same scheme as
make_annotation_sheets. Keep KEY_DO_NOT_OPEN.csv closed until labels are frozen.
The pilot preliminary labels were proposed by an AI annotator; the comparison
is a sanity check on the rubric, never a result.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from pathlib import Path

import pandas as pd

from common import ROOT, read_jsonl
from evaluate import agreement, cohen_kappa, derive, gwet_ac1, md
from make_annotation_sheets import LABEL_COLUMNS
from verify import load_sources

PILOT_OUTPUTS = ROOT / "pilot" / "pilot_outputs.jsonl"
PRELIMINARY = ROOT / "pilot" / "pilot_annotations_PRELIMINARY.csv"
DEFAULT_OUT = ROOT / "data" / "calibration" / "pilot"
SHEET_COLUMNS = ["annotation_id", "transformation_requested", "model_status", "original", "adaptation", *LABEL_COLUMNS]
KEY_COLUMNS = ["annotation_id", "output_id", "source_id", "generator", "transformation", "partition",
               "is_repair", "repair_of", "double_annotated"]
# labels compared between annotators (free text, evidence and confidence are not)
COMPARED = ["adaptation_needed", "math_fidelity", "target_preserved", "solvability_changed", "ambiguity",
            "leakage_level", "leakage_type", "presentation", "abstention_appropriate", "failure_codes"]
ORDINAL = {"leakage_level", "presentation"}


def short_model(model: str) -> str:
    """'claude-haiku-5-5 (Claude Code subagent)' -> 'claude-haiku-5-5'."""
    return model.split("(")[0].strip()


def annotation_id(output_id: str, seed: int) -> str:
    return "a" + hashlib.sha256(f"{seed}|{output_id}".encode()).hexdigest()[:10]


def pilot_as_generations(rows: list[dict]) -> list[dict]:
    """Adapt pilot/pilot_outputs.jsonl rows to the generations schema used by make_annotation_sheets."""
    return [
        {
            "output_id": r["output_id"], "source_id": r["source_id"], "generator": short_model(r["model"]),
            "model": r["model"], "transformation": r["transformation"], "partition": "dev", "run_id": "pilot",
            "prompt_version": r.get("prompt_version"), "status": r.get("status"),
            "adapted_problem": r.get("adapted_problem") or "",
        }
        for r in rows
    ]


def _sheet_row(it: dict, sources: dict[str, str]) -> dict:
    status = it.get("status") or ""
    return {"annotation_id": it["annotation_id"], "transformation_requested": it["transformation"],
            "model_status": status if status in ("NO_REWRITE_NEEDED", "REWRITTEN") else "",
            "original": sources[it["source_id"]], "adaptation": it["adapted_problem"], **{c: "" for c in LABEL_COLUMNS}}


def make_calibration_sheets(out_dir: Path = DEFAULT_OUT, seed: int = 2880) -> None:
    """Write sheet_A.csv and sheet_B.csv (each with every pilot item, shuffled separately) and KEY_DO_NOT_OPEN.csv."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    sources = load_sources()
    items = [g for g in pilot_as_generations(read_jsonl(PILOT_OUTPUTS)) if g["adapted_problem"]]
    for it in items:
        it["annotation_id"] = annotation_id(it["output_id"], seed)
    for name in ("sheet_A.csv", "sheet_B.csv"):
        rng.shuffle(items)
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
            w.writeheader()
            w.writerows(_sheet_row(i, sources) for i in items)
    with open(out_dir / "KEY_DO_NOT_OPEN.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(KEY_COLUMNS)
        for i in sorted(items, key=lambda x: x["annotation_id"]):
            w.writerow([i["annotation_id"], i["output_id"], i["source_id"], i["generator"], i["transformation"],
                        i["partition"], False, "", True])
    print(f"{len(items)} pilot items -> sheet_A and sheet_B (both complete); written to {out_dir}")


# ------------------------------------------------------------------ agreement

def _norm(v) -> str:
    """Canonical string for a label cell: blanks -> '', 1.0 -> '1', ' PASS ' -> 'PASS'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    try:
        x = float(s)
        return str(int(x)) if x.is_integer() else s
    except ValueError:
        return s


def _read_labels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in COMPARED:
        if c in df:
            df[c] = df[c].map(_norm)
    return df


def _extra_rows(m: pd.DataFrame, labels: list[str], suffixes=("_a", "_b")) -> list[dict]:
    rows = []
    for col in labels:
        x, y = m[f"{col}{suffixes[0]}"].map(_norm), m[f"{col}{suffixes[1]}"].map(_norm)
        keep = (x != "") & (y != "")
        x, y = x[keep], y[keep]
        w = "quadratic" if col in ORDINAL else None
        rows.append({"label": col, "n": int(keep.sum()),
                     "raw_agreement": float((x.values == y.values).mean()) if keep.any() else float("nan"),
                     "kappa": cohen_kappa(x, y, w) if keep.any() else float("nan"), "kappa_weighting": w or "none",
                     "gwet_ac1": gwet_ac1(x, y) if keep.any() else float("nan")})
    return rows


def agreement_report(a_csv: Path, b_csv: Path) -> pd.DataFrame:
    """evaluate.agreement on the derived outcomes, plus the remaining rubric labels; printed as markdown."""
    a, b = (derive(_read_labels(Path(p))) for p in (a_csv, b_csv))
    m = a.merge(b, on="annotation_id", suffixes=("_a", "_b"))
    try:
        table = agreement(a, b)
    except ValueError:  # a label column still blank in one sheet (sheets not finished)
        table = pd.DataFrame(_extra_rows(m, ["math_fidelity", "target_preserved", "ambiguity", "leakage_level",
                                             "presentation", "SAFE"]))
    rest = [c for c in COMPARED if c not in set(table["label"]) and f"{c}_a" in m]
    table = pd.concat([table, pd.DataFrame(_extra_rows(m, rest))], ignore_index=True)
    print("## Calibration agreement (A vs B, all pilot items)\n")
    print(md(table))
    return table


def disagreements(a_csv: Path, b_csv: Path, key_csv: Path, out: Path | None = None) -> pd.DataFrame:
    """One row per (annotation_id, label) with A != B, with both evidences, the texts and the key fields."""
    a, b = _read_labels(Path(a_csv)), _read_labels(Path(b_csv))
    key = pd.read_csv(key_csv, dtype=str, keep_default_na=False)
    m = a.merge(b, on="annotation_id", suffixes=("_A", "_B")).merge(key, on="annotation_id", how="left")
    rows = []
    for _, r in m.iterrows():
        for label in COMPARED:
            if f"{label}_A" not in m:
                continue
            if r[f"{label}_A"] != r[f"{label}_B"]:
                rows.append({"annotation_id": r["annotation_id"], "label": label, "A": r[f"{label}_A"],
                             "B": r[f"{label}_B"], "evidence_A": r.get("evidence_A", ""),
                             "evidence_B": r.get("evidence_B", ""), "notes_A": r.get("notes_A", ""),
                             "notes_B": r.get("notes_B", ""), "original": r.get("original_A", ""),
                             "adaptation": r.get("adaptation_A", ""), "output_id": r.get("output_id", ""),
                             "source_id": r.get("source_id", ""), "generator": r.get("generator", ""),
                             "transformation": r.get("transformation", ""), "partition": r.get("partition", "")})
    cols = ["annotation_id", "label", "A", "B", "evidence_A", "evidence_B", "notes_A", "notes_B", "original",
            "adaptation", "output_id", "source_id", "generator", "transformation", "partition"]
    df = pd.DataFrame(rows, columns=cols).sort_values(["label", "annotation_id"]).reset_index(drop=True)
    out = Path(out) if out else Path(a_csv).parent / "disagreements.csv"
    df.to_csv(out, index=False)
    print(f"{len(df)} disagreements on {df['annotation_id'].nunique()} items -> {out}")
    return df


def compare_to_preliminary(adjudicated_csv: Path, key_csv: Path, preliminary_csv: Path = PRELIMINARY) -> pd.DataFrame:
    """Per-label agreement between the human adjudicated labels and the AI preliminary pilot labels."""
    adj = derive(_read_labels(Path(adjudicated_csv)))
    adj = adj.drop(columns=[c for c in ("output_id", "source_id") if c in adj])  # the key is authoritative
    key = pd.read_csv(key_csv, dtype=str, keep_default_na=False)
    pre = derive(_read_labels(Path(preliminary_csv)))
    m = adj.merge(key[["annotation_id", "output_id"]], on="annotation_id").merge(pre, on="output_id",
                                                                               suffixes=("_human", "_ai"))
    labels = [c for c in COMPARED if f"{c}_human" in m and f"{c}_ai" in m] + ["SAFE", "SAFE_AND_USEFUL"]
    table = pd.DataFrame(_extra_rows(m, labels, ("_human", "_ai")))
    print(f"## Human adjudicated vs AI preliminary labels (n = {len(m)} matched items)\n")
    print(md(table))
    return table


# ------------------------------------------------------------------ cli

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--make-sheets", action="store_true")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=2880)
    ap.add_argument("--agreement", nargs=2, metavar=("A_CSV", "B_CSV"))
    ap.add_argument("--disagreements", nargs=3, metavar=("A_CSV", "B_CSV", "KEY_CSV"))
    ap.add_argument("--compare-preliminary", nargs=2, metavar=("ADJ_CSV", "KEY_CSV"))
    args = ap.parse_args()
    if args.make_sheets:
        make_calibration_sheets(Path(args.out), args.seed)
    if args.agreement:
        agreement_report(*map(Path, args.agreement))
    if args.disagreements:
        disagreements(*map(Path, args.disagreements))
    if args.compare_preliminary:
        compare_to_preliminary(*map(Path, args.compare_preliminary))
    if not (args.make_sheets or args.agreement or args.disagreements or args.compare_preliminary):
        ap.print_help()


if __name__ == "__main__":
    main()
