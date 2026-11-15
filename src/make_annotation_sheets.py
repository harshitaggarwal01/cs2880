"""Build blinded annotation sheets.

  python src/make_annotation_sheets.py data/outputs/main-v1/generations.jsonl [repairs.jsonl ...] \
      --double-frac 0.30 --seed 2880
  python src/make_annotation_sheets.py <files> --config config.matrix.yaml     # labelling plan from the config

Two designs (config block `labelling:`; without it the design is "full"):

  full   sheet_A = every item; sheet_B = a stratified double-annotation subset (generator x transformation x
         partition x repair). One annotator labels everything.
  lean   (prespecified 2026-11-15, Option 2) only a planned subset is labelled, split between two annotators:
         - which items: per transformation, a fraction of SOURCE problems, drawn once per (partition, step bucket)
           stratum from one random order of sources, so the samples are nested (a smaller fraction is a subset of
           a larger one) and every labelled source has all of its rewrites labelled for that transformation. This
           keeps comparisons across generators and styles paired on the same sources. Default fractions:
           plain 0.5, chunked 0.5, naive (realistic prompt) 1.0, deterministic baseline 0.3.
         - repairs are labelled exactly when the output they repair is labelled.
         - double annotation: a stratified `double_frac` of the labelled items goes to both annotators; the rest is
           split evenly, stratum by stratum. sheet_A / sheet_B hold each annotator's items plus the shared ones.
         Unlabelled items are not on any sheet; their rates come from prediction-powered inference with the
         primary verifier as predictor (src/ppi.py), and hypothesis tests use labelled items only.

Writes to data/annotations/<run>/:
  sheet_A.csv, sheet_B.csv      blinded items for each annotator
  KEY_DO_NOT_OPEN.csv           annotation_id -> output_id/generator/transformation/repair flag/assignment
  LABEL_PLAN.json               design, fractions, counts per stratum and per annotator, estimated hours
Annotators must not open the key until labels are frozen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from common import FROZEN, ROOT, read_jsonl, step_bucket
from verify import load_sources

LABEL_COLUMNS = ["adaptation_needed", "math_fidelity", "target_preserved", "solvability_changed", "ambiguity",
                 "leakage_level", "leakage_type", "presentation", "abstention_appropriate", "failure_codes",
                 "evidence", "confidence", "notes"]
DEFAULT_LEAN = {"design": "lean", "label_frac": {"plain": 0.5, "chunked": 0.5, "naive": 1.0, "deterministic": 0.3},
                "double_frac": 0.30, "minutes_per_item": 1.5}


def annotation_id(output_id: str, seed: int) -> str:
    return "a" + hashlib.sha256(f"{seed}|{output_id}".encode()).hexdigest()[:10]


def is_repair(it: dict) -> bool:
    return "repair_of" in it


def source_strata() -> dict[str, tuple[str, str]]:
    """source_id -> (partition, step bucket) from the frozen sample (unknown n_steps -> 'na')."""
    out = {}
    for p in FROZEN.glob("*.jsonl"):
        for r in read_jsonl(p):
            n = r.get("n_steps")
            out[r["source_id"]] = (r.get("partition") or p.stem, step_bucket(int(n)) if n is not None else "na")
    return out


def source_order(source_ids: set[str], strata: dict[str, tuple[str, str]], rng: random.Random) -> dict[str, float]:
    """Each source's quantile rank (0..1) within its stratum, from one random order. A transformation with label
    fraction f labels the sources whose rank is < f (rounded per stratum), so samples are nested across f."""
    groups = defaultdict(list)
    for s in sorted(source_ids):
        groups[strata.get(s, ("unknown", "na"))].append(s)
    rank = {}
    for key in sorted(groups):
        g = groups[key]
        rng.shuffle(g)
        for i, s in enumerate(g):
            rank[s] = (i + 0.5) / len(g)
    return rank


def plan_labelled(items: list[dict], plan: dict, rng: random.Random,
                  strata: dict[str, tuple[str, str]] | None = None) -> set[str]:
    """annotation_ids to label under the lean design (see module docstring)."""
    strata = strata if strata is not None else source_strata()
    fracs = plan.get("label_frac", {})
    firsts = [it for it in items if not is_repair(it)]
    rank = source_order({it["source_id"] for it in firsts}, strata, rng)
    # per stratum, label the first round(f * n) sources: rank < f with a half-step tolerance gives exactly that
    sizes = Counter(strata.get(s, ("unknown", "na")) for s in rank)
    labelled_out = set()
    for it in firsts:
        tf = "deterministic" if it.get("generator") == "deterministic" else it["transformation"]
        f = float(fracs.get(tf, 1.0))
        n = sizes[strata.get(it["source_id"], ("unknown", "na"))]
        k = round(f * n)
        if rank[it["source_id"]] * n < k:
            labelled_out.add(it["output_id"])
    for it in items:
        if is_repair(it) and it["repair_of"] in labelled_out:
            labelled_out.add(it["output_id"])
    return {it["annotation_id"] for it in items if it["output_id"] in labelled_out}


def stratum(it: dict) -> tuple:
    return it["generator"], it["transformation"], it["partition"], is_repair(it)


def pick_double(items: list[dict], frac: float, rng: random.Random) -> set[str]:
    groups = defaultdict(list)
    for it in items:
        groups[stratum(it)].append(it)
    double = set()
    for key in sorted(groups, key=str):
        g = groups[key]
        k = max(1, round(len(g) * frac))
        double |= {it["annotation_id"] for it in rng.sample(g, k)}
    return double


def split_annotators(items: list[dict], double: set[str], rng: random.Random) -> dict[str, str]:
    """annotation_id -> 'AB' (both), 'A' or 'B'; single items alternate A/B within each stratum."""
    out = {a: "AB" for a in double}
    groups = defaultdict(list)
    for it in items:
        if it["annotation_id"] not in double:
            groups[stratum(it)].append(it)
    turn = 0
    for key in sorted(groups, key=str):
        g = groups[key]
        rng.shuffle(g)
        for it in g:
            out[it["annotation_id"]] = "AB"[turn % 2]
            turn += 1
    return out


def load_plan(config: str | None, design: str | None) -> dict:
    cfg = yaml.safe_load(Path(config).read_text()) if config else {}
    plan = dict(cfg.get("labelling") or {})
    if design == "lean" and plan.get("design") != "lean":
        plan = {**DEFAULT_LEAN, **{k: v for k, v in plan.items() if k != "design"}, "design": "lean"}
    if design == "full":
        plan["design"] = "full"
    plan.setdefault("design", "full")
    if plan["design"] == "lean":
        plan = {**DEFAULT_LEAN, **plan, "label_frac": {**DEFAULT_LEAN["label_frac"], **plan.get("label_frac", {})}}
    plan.setdefault("minutes_per_item", cfg.get("minutes_per_review", 1.5))
    return plan


def build(files: list[str], plan: dict, double_frac: float, seed: int, out_dir: Path | None = None,
          strata: dict | None = None) -> dict:
    rng = random.Random(seed)
    src = load_sources()
    items = [g for f in files for g in read_jsonl(Path(f)) if g.get("adapted_problem")]
    run = items[0].get("run_id", "run")
    out_dir = out_dir or ROOT / "data" / "annotations" / run
    out_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        it["annotation_id"] = annotation_id(it["output_id"], seed)
    rng.shuffle(items)

    if plan["design"] == "lean":
        labelled = plan_labelled(items, plan, rng, strata)
        lab_items = [it for it in items if it["annotation_id"] in labelled]
        double = pick_double(lab_items, float(plan.get("double_frac", double_frac)), rng)
        assign = split_annotators(lab_items, double, rng)
    else:
        lab_items = items
        double = pick_double(items, double_frac, rng)
        assign = {it["annotation_id"]: ("AB" if it["annotation_id"] in double else "A") for it in items}

    def row(it):
        status = it.get("status") or ""
        return {"annotation_id": it["annotation_id"], "transformation_requested": it["transformation"],
                "model_status": status if status in ("NO_REWRITE_NEEDED", "REWRITTEN") else "",
                "original": src[it["source_id"]], "adaptation": it["adapted_problem"], **{c: "" for c in LABEL_COLUMNS}}

    sheets = {"sheet_A.csv": [i for i in lab_items if "A" in assign[i["annotation_id"]]],
              "sheet_B.csv": [i for i in lab_items if "B" in assign[i["annotation_id"]]]}
    for name, subset in sheets.items():
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row(lab_items[0])))
            w.writeheader()
            w.writerows(row(i) for i in subset)
    with open(out_dir / "KEY_DO_NOT_OPEN.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["annotation_id", "output_id", "source_id", "generator", "transformation", "partition",
                    "is_repair", "repair_of", "double_annotated", "assigned_to"])
        for i in lab_items:
            w.writerow([i["annotation_id"], i["output_id"], i["source_id"], i["generator"], i["transformation"],
                        i["partition"], is_repair(i), i.get("repair_of", ""), i["annotation_id"] in double,
                        assign[i["annotation_id"]]])
    minutes = float(plan.get("minutes_per_item", 1.5))
    by_stratum = Counter(f"{g}|{t}|{p}|{'repair' if r else 'first'}" for g, t, p, r in map(stratum, items))
    lab_stratum = Counter(f"{g}|{t}|{p}|{'repair' if r else 'first'}" for g, t, p, r in map(stratum, lab_items))
    summary = {"design": plan["design"], "seed": seed, "label_frac": plan.get("label_frac"),
               "double_frac": float(plan.get("double_frac", double_frac)), "n_items": len(items),
               "n_labelled": len(lab_items), "n_double": len(double),
               "per_annotator": {a: len(v) for a, v in (("A", sheets["sheet_A.csv"]), ("B", sheets["sheet_B.csv"]))},
               "hours_per_annotator": {a: round(len(v) * minutes / 60, 1)
                                       for a, v in (("A", sheets["sheet_A.csv"]), ("B", sheets["sheet_B.csv"]))},
               "minutes_per_item": minutes,
               "strata": {k: {"items": by_stratum[k], "labelled": lab_stratum.get(k, 0)} for k in sorted(by_stratum)}}
    (out_dir / "LABEL_PLAN.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{plan['design']} design: {len(items)} items, {len(lab_items)} labelled ({len(double)} by both); "
          f"A {summary['per_annotator']['A']} items (~{summary['hours_per_annotator']['A']} h), "
          f"B {summary['per_annotator']['B']} items (~{summary['hours_per_annotator']['B']} h); written to {out_dir}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--double-frac", type=float, default=0.30)
    ap.add_argument("--seed", type=int, default=2880)
    ap.add_argument("--config", help="read the `labelling:` block (design, label_frac, double_frac)")
    ap.add_argument("--design", choices=("full", "lean"), help="override the config's design")
    args = ap.parse_args()
    build(args.files, load_plan(args.config, args.design), args.double_frac, args.seed)


if __name__ == "__main__":
    main()
