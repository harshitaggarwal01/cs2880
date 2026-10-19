"""Build blinded annotation sheets.

  python src/make_annotation_sheets.py data/outputs/main-v1/generations.jsonl [repairs.jsonl ...] \
      --double-frac 0.30 --seed 2880

Writes to data/annotations/<run>/:
  sheet_A.csv   every item (shuffled, blinded)
  sheet_B.csv   stratified double-annotation subset (model x transformation x partition)
  KEY_DO_NOT_OPEN.csv   annotation_id -> output_id/model/transformation/repair flag
Annotators must not open the key until labels are frozen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

from common import ROOT, read_jsonl
from verify import load_sources

LABEL_COLUMNS = ["adaptation_needed", "math_fidelity", "target_preserved", "solvability_changed", "ambiguity",
                 "leakage_level", "leakage_type", "presentation", "abstention_appropriate", "failure_codes",
                 "evidence", "confidence", "notes"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--double-frac", type=float, default=0.30)
    ap.add_argument("--seed", type=int, default=2880)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    src = load_sources()
    items = [g for f in args.files for g in read_jsonl(Path(f)) if g.get("adapted_problem")]
    run = items[0].get("run_id", "run")
    out_dir = ROOT / "data" / "annotations" / run
    out_dir.mkdir(parents=True, exist_ok=True)

    for it in items:
        it["annotation_id"] = "a" + hashlib.sha256(f"{args.seed}|{it['output_id']}".encode()).hexdigest()[:10]
    rng.shuffle(items)

    strata = defaultdict(list)
    for it in items:
        strata[(it["generator"], it["transformation"], it["partition"], "repair_of" in it)].append(it)
    double = set()
    for group in strata.values():
        k = max(1, round(len(group) * args.double_frac))
        double |= {it["annotation_id"] for it in rng.sample(group, k)}

    def row(it):
        status = it.get("status") or ""
        return {"annotation_id": it["annotation_id"], "transformation_requested": it["transformation"],
                "model_status": status if status in ("NO_REWRITE_NEEDED", "REWRITTEN") else "",
                "original": src[it["source_id"]], "adaptation": it["adapted_problem"], **{c: "" for c in LABEL_COLUMNS}}

    for name, subset in (("sheet_A.csv", items), ("sheet_B.csv", [i for i in items if i["annotation_id"] in double])):
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row(items[0])))
            w.writeheader()
            w.writerows(row(i) for i in subset)
    with open(out_dir / "KEY_DO_NOT_OPEN.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["annotation_id", "output_id", "source_id", "generator", "transformation", "partition",
                    "is_repair", "repair_of", "double_annotated"])
        for i in items:
            w.writerow([i["annotation_id"], i["output_id"], i["source_id"], i["generator"], i["transformation"],
                        i["partition"], "repair_of" in i, i.get("repair_of", ""), i["annotation_id"] in double])
    print(f"{len(items)} items -> sheet_A; {len(double)} double-annotated -> sheet_B; written to {out_dir}")


if __name__ == "__main__":
    main()
