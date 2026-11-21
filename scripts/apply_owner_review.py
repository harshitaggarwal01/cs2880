"""Apply the owner's review of the calibration adjudications (replaces the 2026-11-19 AI adjudications).

  python scripts/apply_owner_review.py data/calibration/pilot/owner_review_2026-11-20.csv
  python src/adjudicate.py --ann data/calibration/pilot --resolved TO_ADJUDICATE.csv

Per item: OVERRIDE writes every non-empty label column (and failure_codes) into the *_final columns of
TO_ADJUDICATE.csv; ACCEPT keeps the final labels. notes_final records the owner's decision and comment. The script
fails if the derived SAFE of any overridden item differs from the owner's SAFE_owner, or if a final row breaks the
rubric's validation rules.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sheets_xlsx import SHOWN, validate  # noqa: E402

LABELS = ["adaptation_needed", "math_fidelity", "target_preserved", "solvability_changed", "ambiguity",
          "leakage_level", "leakage_type", "presentation", "abstention_appropriate", "failure_codes"]
DATE = "2026-11-20"


def safe(r: pd.Series) -> bool:
    return (r.math_fidelity_final == "PASS" and r.target_preserved_final == "PASS"
            and r.solvability_changed_final == "NO" and r.ambiguity_final != "NEW"
            and str(r.leakage_level_final).strip() == "0")


def main(review_csv: str, adj_csv: str = "data/calibration/pilot/TO_ADJUDICATE.csv") -> None:
    rev = pd.read_csv(review_csv, dtype=str, keep_default_na=False)
    adj = pd.read_csv(adj_csv, dtype=str, keep_default_na=False)
    missing = set(adj.annotation_id) - set(rev.annotation_id)
    if missing:
        raise SystemExit(f"owner review lacks {len(missing)} items: {sorted(missing)}")
    problems = []
    for _, r in rev.iterrows():
        i = adj.index[adj.annotation_id == r.annotation_id][0]
        if r.decision == "OVERRIDE":
            for c in LABELS:
                if r[c] != "":
                    adj.at[i, f"{c}_final"] = r[c]
        elif r.decision != "ACCEPT":
            raise SystemExit(f"{r.annotation_id}: decision must be ACCEPT or OVERRIDE, got {r.decision!r}")
        adj.at[i, "notes_final"] = f"Owner adjudication {DATE} ({r.decision}): {r.comment}"
        row = adj.loc[i]
        if r.SAFE_owner and (safe(row) != (r.SAFE_owner == "YES")):
            problems.append(f"{r.annotation_id}: derived SAFE {safe(row)} but owner SAFE {r.SAFE_owner}")
        rec = {**{c: row[c] for c in SHOWN if c in row}, **{c: row[f"{c}_final"] for c in LABELS + ["evidence", "confidence", "notes"]}}
        _, probs, _ = validate(rec)
        problems += [f"{r.annotation_id}: {p}" for p in probs]
    if problems:
        raise SystemExit("not applied:\n  " + "\n  ".join(problems))
    adj.to_csv(adj_csv, index=False)
    print(f"applied owner review to {adj_csv}: {rev.decision.value_counts().to_dict()}")


if __name__ == "__main__":
    main(*sys.argv[1:])
