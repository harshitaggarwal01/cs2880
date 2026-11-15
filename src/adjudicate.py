"""Merge the two annotators' sheets into adjudicated.csv (works for the full and the lean design).

  python src/adjudicate.py --ann data/annotations/matrix-v1                 # step 1: merge + list disagreements
  # both annotators resolve TO_ADJUDICATE.csv together (fill the *_final columns), then:
  python src/adjudicate.py --ann data/annotations/matrix-v1 --resolved TO_ADJUDICATE.csv   # step 2: final file

Rules
  - an item labelled by one annotator only: that label is final;
  - an item labelled by both: if they agree on every KEY label, that label is final; otherwise the item goes to
    TO_ADJUDICATE.csv (both answers side by side, `*_final` columns to fill) and is final only after step 2;
  - unlabelled cells count as disagreement on a KEY label (an item must be fully labelled to be final).
Agreement (Cohen's kappa / Gwet's AC1) is computed BEFORE adjudication by `evaluate.agreement` on the shared items;
this script prints it too. Output: adjudicated.csv with annotator = "ADJ" on every row (evaluate.load_labels keeps
only ADJ rows), plus `source` = A | B | agreed | adjudicated for transparency.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from make_annotation_sheets import LABEL_COLUMNS

KEY_LABELS = ["math_fidelity", "target_preserved", "solvability_changed", "ambiguity", "leakage_level", "presentation"]
META = ["annotation_id", "transformation_requested", "model_status", "original", "adaptation"]


def _filled(v) -> bool:
    return not (pd.isna(v) or str(v).strip() == "")


def _done(row: pd.Series, suffix: str = "") -> bool:
    return all(_filled(row.get(c + suffix)) for c in KEY_LABELS)


def merge(sheet_a: Path, sheet_b: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """(final rows, rows needing adjudication, warnings)."""
    a, b = pd.read_csv(sheet_a, dtype=str), pd.read_csv(sheet_b, dtype=str)
    warn = []
    both = set(a["annotation_id"]) & set(b["annotation_id"])
    final, todo = [], []
    for name, df, other in (("A", a, b), ("B", b, a)):
        for _, r in df[~df["annotation_id"].isin(both)].iterrows():
            if _done(r):
                final.append({**r.to_dict(), "source": name})
            else:
                warn.append(f"{r['annotation_id']}: not fully labelled by {name}")
    m = a[a["annotation_id"].isin(both)].merge(b[b["annotation_id"].isin(both)], on=META, suffixes=("_A", "_B"))
    for _, r in m.iterrows():
        if _done(r, "_A") and _done(r, "_B") and all(str(r[c + "_A"]).strip() == str(r[c + "_B"]).strip()
                                                     for c in KEY_LABELS):
            final.append({**{c: r[c] for c in META}, **{c: r[c + "_A"] for c in LABEL_COLUMNS}, "source": "agreed"})
        else:
            todo.append({**{c: r[c] for c in META},
                         **{f"{c}_{s}": r[f"{c}_{s}"] for c in LABEL_COLUMNS for s in ("A", "B")},
                         **{f"{c}_final": "" for c in LABEL_COLUMNS}})
    return pd.DataFrame(final), pd.DataFrame(todo), warn


def apply_resolved(final: pd.DataFrame, resolved: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    rows, warn = [], []
    for _, r in resolved.iterrows():
        vals = {c: r.get(f"{c}_final") for c in LABEL_COLUMNS}
        if not all(_filled(vals[c]) for c in KEY_LABELS):
            warn.append(f"{r['annotation_id']}: *_final key labels not all filled")
            continue
        rows.append({**{c: r[c] for c in META}, **vals, "source": "adjudicated"})
    return pd.concat([final, pd.DataFrame(rows)], ignore_index=True), warn


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ann", required=True, help="data/annotations/<run_id>")
    ap.add_argument("--resolved", help="TO_ADJUDICATE.csv with *_final columns filled")
    args = ap.parse_args()
    ann = Path(args.ann)
    for name in ("sheet_A", "sheet_B"):  # labels entered in the .xlsx sheets are imported (validated) first
        x, c = ann / f"{name}.xlsx", ann / f"{name}.csv"
        if x.exists() and (not c.exists() or x.stat().st_mtime > c.stat().st_mtime):
            from sheets_xlsx import import_xlsx
            done, probs = import_xlsx(x, partial=True)
            print(f"imported {x.name}: {done} labelled rows" + (f", {len(probs)} problems (run make import-sheets)"
                                                                  if probs else ""))
    final, todo, warn = merge(ann / "sheet_A.csv", ann / "sheet_B.csv")
    try:
        from evaluate import agreement, derive
        ag = agreement(derive(pd.read_csv(ann / "sheet_A.csv")), derive(pd.read_csv(ann / "sheet_B.csv")))
        print("## Agreement before adjudication\n")
        print(ag.to_string(index=False), "\n")
    except Exception as e:  # noqa: BLE001 - agreement needs labelled overlap; report and continue
        print(f"(agreement not computed: {type(e).__name__}: {e})")
    if args.resolved:
        final, w2 = apply_resolved(final, pd.read_csv(ann / args.resolved if not Path(args.resolved).exists()
                                                      else args.resolved, dtype=str))
        warn += w2
        todo = todo.iloc[0:0]
    for w in warn:
        print("WARNING:", w)
    if len(todo):
        todo.to_csv(ann / "TO_ADJUDICATE.csv", index=False)
        print(f"{len(todo)} items need joint adjudication -> {ann / 'TO_ADJUDICATE.csv'}; "
              f"{len(final)} final so far. Re-run with --resolved TO_ADJUDICATE.csv when done.")
        return
    out = final.assign(annotator="ADJ")
    out.to_csv(ann / "adjudicated.csv", index=False)
    print(f"adjudicated.csv: {len(out)} items ({out['source'].value_counts().to_dict()})")


if __name__ == "__main__":
    main()
