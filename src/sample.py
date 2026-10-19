"""Freeze the source-problem sample (run once, before any generation).

Partitions
  dev       10 GSM8K *train* problems   prompt/rubric/verifier development only
  main     100 GSM8K *test* problems    primary paired evaluation (stratified)
  ext_gsm1k 12 GSM1K problems           newer GSM8K-style problems (contamination check)
  ext_asdiv 12 ASDiv problems           different linguistic/problem-type distribution

Main sample: stratified by reasoning-step bucket (from the GSM8K solution's
calculator annotations) x whether the text contains a relational cue
(comparison, fraction, percent), proportional allocation with a floor.

Usage:  python src/sample.py [--seed 2880]
GSM1K text is not redistributed (no license declared on its dataset card);
only row indices are frozen. Fetch the text with src/fetch_data.py --gsm1k.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict

from common import FROZEN, load_asdiv, load_gsm8k, relational, sha256_text, step_bucket, tags, write_jsonl

GSM1K_ROWS = 1205
ASDIV_TYPES = [
    "Subtraction", "Addition", "Multiplication", "Common-Division", "Ratio", "Comparison",
    "Surplus", "TVQ-Change", "Sequential-Operation", "Algebra-1", "Difference", "Ceil-Division",
]


def allocate(cells: dict[str, list], total: int, floor: int) -> dict[str, int]:
    n = sum(len(v) for v in cells.values())
    alloc = {k: max(floor, round(total * len(v) / n)) for k, v in cells.items()}
    # trim/pad the largest cells until the allocation sums to total
    order = sorted(cells, key=lambda k: -len(cells[k]))
    i = 0
    while sum(alloc.values()) != total:
        k = order[i % len(order)]
        step = -1 if sum(alloc.values()) > total else 1
        if alloc[k] + step >= floor:
            alloc[k] += step
        i += 1
    return alloc


def record(p: dict, partition: str) -> dict:
    r = {k: p[k] for k in ("source_id", "dataset", "split", "row", "text", "answer")}
    r.update(partition=partition, source_sha256=sha256_text(p["text"]), tags=tags(p["text"]))
    if "n_steps" in p:
        r["n_steps"] = p["n_steps"]
    if "solution_type" in p:
        r["solution_type"] = p["solution_type"]
        r["grade"] = p["grade"]
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2880)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # ---- main: stratified GSM8K test
    test = load_gsm8k("test")
    cells: dict[str, list] = defaultdict(list)
    for p in test:
        cells[f"{step_bucket(p['n_steps'])}|rel={relational(p['text'])}"].append(p)
    alloc = allocate(cells, 100, floor=6)
    main_rows = []
    for key in sorted(cells):
        main_rows += [record(p, "main") for p in rng.sample(cells[key], alloc[key])]

    # ---- dev: GSM8K train, 10 problems spread over step buckets, half relational
    train = load_gsm8k("train")
    dev_rows, used = [], set()
    plan = [("s<=2", False), ("s<=2", True), ("s=3", False), ("s=3", True), ("s=4", False),
            ("s=4", True), ("s>=5", False), ("s>=5", True), ("s=3", True), ("s=4", True)]
    for bucket, rel in plan:
        pool = [p for p in train if step_bucket(p["n_steps"]) == bucket and relational(p["text"]) == rel
                and p["source_id"] not in used]
        p = rng.choice(pool)
        used.add(p["source_id"])
        dev_rows.append(record(p, "dev"))

    # ---- external: ASDiv, one problem per solution type, grades 3-6
    asdiv = load_asdiv()
    asdiv_rows = []
    for st in ASDIV_TYPES:
        pool = [p for p in asdiv if p["solution_type"] == st and p["grade"] >= 3] or \
               [p for p in asdiv if p["solution_type"] == st]
        asdiv_rows.append(record(rng.choice(pool), "ext_asdiv"))

    # ---- external: GSM1K row indices only
    gsm1k_rows = [
        {"source_id": f"gsm1k-test-{i:04d}", "dataset": "gsm1k", "split": "test", "row": i,
         "partition": "ext_gsm1k", "text": None, "source_sha256": None}
        for i in sorted(rng.sample(range(GSM1K_ROWS), 12))
    ]

    FROZEN.mkdir(parents=True, exist_ok=True)
    write_jsonl(FROZEN / "dev.jsonl", dev_rows)
    write_jsonl(FROZEN / "main.jsonl", main_rows)
    write_jsonl(FROZEN / "ext_asdiv.jsonl", asdiv_rows)
    write_jsonl(FROZEN / "ext_gsm1k_ids.jsonl", gsm1k_rows)
    manifest = {
        "seed": args.seed,
        "counts": {"dev": len(dev_rows), "main": len(main_rows), "ext_asdiv": len(asdiv_rows),
                   "ext_gsm1k": len(gsm1k_rows)},
        "main_allocation": alloc,
        "main_tag_coverage": dict(Counter(k for r in main_rows for k, v in r["tags"].items() if v)),
        "main_step_buckets": dict(Counter(step_bucket(r["n_steps"]) for r in main_rows)),
    }
    (FROZEN / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
