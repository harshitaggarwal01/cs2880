"""Generation-variance check: regenerate a small sample once and measure how often the outcome flips.

  python src/variance_check.py --config config.yaml [--mock] [--n 20]

Picks n main-partition sources (seeded), regenerates every generator x transformation for them under run_id
"<run_id>-var" (kept apart from the main outputs, which are never overwritten), runs the deterministic verifier on the
new text, and reports how often the adapted text, the deterministic decision and (when both sides have the same
layers) the full verifier decision differ from the original generation. Also writes a small blinded CSV so a human
can check whether SAFE labels flip between the original and the regenerated adaptation.

Output (under data/outputs/<run_id>/variance/): variance_generations.jsonl, variance_generations.verify-det.jsonl,
variance_flip_rates.json, flip_check_sheet.csv, flip_check_sheet_KEY.csv. This is a stability estimate for the
write-up; it never replaces the first response of the main run.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
from pathlib import Path

import yaml

import collect_outputs
from common import FROZEN, OUTPUTS, ROOT, read_jsonl
from evaluate import write_analysis


def pick(main_sources: list[dict], n: int = 20, seed: int = 2880) -> list[dict]:
    """Seeded sample of n sources (all if fewer), returned sorted by source_id."""
    pool = sorted((s for s in main_sources if s.get("text")), key=lambda s: s["source_id"])
    return sorted(random.Random(seed).sample(pool, min(n, len(pool))), key=lambda s: s["source_id"])


def regenerate(cfg: dict, picked: list[dict], run_dir: Path, mock: bool) -> Path:
    """Regenerate all configured transformations (plus the ablation's) for `picked` with collect_outputs.run."""
    out_path = Path(run_dir) / "variance" / "variance_generations.jsonl"
    var_cfg = {**cfg, "run_id": f"{cfg['run_id']}-var"}
    transformations = list(dict.fromkeys(list(cfg["transformations"]) + [(cfg.get("ablation") or {}).get("transformation")]))
    transformations = [t for t in transformations if t]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    collect_outputs.run(var_cfg, picked, transformations, out_path, mock)
    return out_path


def _norm(text: str | None) -> str | None:
    return " ".join(text.split()) if text else None


def _key(row: dict) -> tuple[str, str, str]:
    return row["generator"], row["transformation"], row["source_id"]


def _rate(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else float("nan")


def flip_rates(orig_gens: list[dict], regen_gens: list[dict], verify_orig: list[dict], verify_regen: list[dict]) -> dict:
    """Agreement of regenerated vs original outputs, matched on (generator, transformation, source_id).

    text_identical_rate: adapted text equal after whitespace normalisation (pairs where both have text).
    det_decision_flip_rate: deterministic-layer decision (PASS/REVIEW/REJECT) differs.
    full_decision_flip_rate: overall verifier decision differs; only pairs whose verification used the same layers.
    Returns {"overall": {...}, "by_condition": {"generator|transformation": {...}}}; each entry has n_pairs, n_verified
    and the three rates (NaN when no pair qualifies).
    """
    regen = {_key(g): g for g in regen_gens}
    vo = {v["output_id"]: v for v in verify_orig}
    vr = {v["output_id"]: v for v in verify_regen}
    per: dict[str, dict[str, list]] = {}
    for g in orig_gens:
        r = regen.get(_key(g))
        if r is None:
            continue
        cond = f"{g['generator']}|{g['transformation']}"
        for scope in (cond, "__overall__"):
            acc = per.setdefault(scope, {"same": [], "det": [], "full": [], "pairs": 0})
            acc["pairs"] += 1
            a, b = _norm(g.get("adapted_problem")), _norm(r.get("adapted_problem"))
            if a is not None or b is not None:
                acc["same"].append(a == b)
            o, n = vo.get(g["output_id"]), vr.get(r["output_id"])
            if o and n:
                acc["det"].append(o["deterministic"]["decision"] != n["deterministic"]["decision"])
                if sorted(o.get("layers") or []) == sorted(n.get("layers") or []):
                    acc["full"].append(o["decision"] != n["decision"])

    def summarize(acc: dict) -> dict:
        return {"n_pairs": acc["pairs"], "n_verified": len(acc["det"]), "text_identical_rate": _rate(acc["same"]),
                "det_decision_flip_rate": _rate(acc["det"]), "full_decision_flip_rate": _rate(acc["full"])}

    overall = per.pop("__overall__", {"same": [], "det": [], "full": [], "pairs": 0})
    return {"overall": summarize(overall), "by_condition": {k: summarize(v) for k, v in sorted(per.items())}}


def make_flip_sheet(orig_gens: list[dict], regen_gens: list[dict], sources: dict, out_csv: Path, seed: int = 2880) -> Path:
    """Blinded CSV for human label-flip checks: original text plus two adaptations in random order, model hidden.

    Only pairs whose text differs are included (identical text cannot flip a label). The order key is written to
    <out_csv stem>_KEY.csv; do not open it before labelling. `sources` maps source_id to text or to a row with text.
    """
    rng = random.Random(seed)
    regen = {_key(g): g for g in regen_gens}
    rows, keyrows = [], []
    for g in sorted(orig_gens, key=_key):
        r = regen.get(_key(g))
        if r is None or not g.get("adapted_problem") or not r.get("adapted_problem"):
            continue
        if _norm(g["adapted_problem"]) == _norm(r["adapted_problem"]):
            continue
        src = sources[g["source_id"]]
        src = src["text"] if isinstance(src, dict) else src
        pid = f"v{len(rows) + 1:03d}"
        first_is_original = rng.random() < 0.5
        x, y = (g, r) if first_is_original else (r, g)
        rows.append({"pair_id": pid, "transformation_requested": g["transformation"], "original": src,
                     "adaptation_X": x["adapted_problem"], "adaptation_Y": y["adapted_problem"],
                     "SAFE_X": "", "SAFE_Y": "", "notes": ""})
        keyrows.append({"pair_id": pid, "X_is": "original" if first_is_original else "regenerated",
                        "output_id": g["output_id"], "generator": g["generator"]})
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    for path, data, cols in ((out_csv, rows, ["pair_id", "transformation_requested", "original", "adaptation_X",
                                              "adaptation_Y", "SAFE_X", "SAFE_Y", "notes"]),
                             (out_csv.with_name(out_csv.stem + "_KEY.csv"), keyrows,
                              ["pair_id", "X_is", "output_id", "generator"])):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(data)
    return out_csv


def det_rows(gens: list[dict], sources: dict) -> list[dict]:
    """Verify-style rows from the deterministic layer only (used when the originals were never verified)."""
    from deterministic_checks import check
    out = []
    for g in gens:
        if g.get("adapted_problem"):
            det = check(sources[g["source_id"]]["text"], g["adapted_problem"], g["transformation"])
            out.append({"output_id": g["output_id"], "layers": ["det"], "decision": det["decision"], "deterministic": det})
    return out


def best_original_verify(run_dir: Path) -> list[dict]:
    """The existing verification of the originals with the most layers, or []."""
    files = sorted(run_dir.glob("generations.verify-*.jsonl"), key=lambda p: -len(p.stem.split(".verify-")[-1].split("-")))
    return read_jsonl(files[0]) if files else []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=2880)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    if args.mock:  # same convention as collect_outputs: dry runs stay out of the real run folder
        cfg["run_id"] += "-mock"
    run_dir = OUTPUTS / cfg["run_id"]
    sources = {r["source_id"]: r for r in read_jsonl(FROZEN / "main.jsonl") if r.get("text")}
    picked = pick(list(sources.values()), args.n, args.seed)
    var_path = regenerate(cfg, picked, run_dir, args.mock)

    verify_path = var_path.with_name("variance_generations.verify-det.jsonl")
    cmd = [sys.executable, str(ROOT / "src" / "verify.py"), str(var_path), "--config", args.config, "--layers", "det",
           "--out", str(verify_path)] + (["--mock"] if args.mock else [])
    subprocess.run(cmd, check=True, cwd=ROOT)

    ids = {s["source_id"] for s in picked}
    orig = [g for f in ("generations.jsonl", "ablation_generations.jsonl") if (run_dir / f).exists()
            for g in read_jsonl(run_dir / f) if g["source_id"] in ids]
    regen = read_jsonl(var_path)
    v_orig = best_original_verify(run_dir) or det_rows(orig, sources)
    rates = flip_rates(orig, regen, v_orig, read_jsonl(verify_path))
    write_analysis(var_path.parent, "variance_flip_rates", rates)   # NaN -> null
    sheet = make_flip_sheet(orig, regen, sources, var_path.parent / "flip_check_sheet.csv", args.seed)
    print(json.dumps(rates["overall"], indent=1, default=float))
    print(f"wrote {var_path.parent}/variance_flip_rates.json and {sheet} (key alongside; do not open before labelling)")


if __name__ == "__main__":
    main()
