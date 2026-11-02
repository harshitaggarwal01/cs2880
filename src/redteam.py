"""Red-team our own verifier: can an attacker leak solution strategy subtly while passing the deterministic layer?

  python src/redteam.py --config config.anthropic.yaml --mock --n 5       # offline plumbing check
  python src/redteam.py --config config.yaml --n 50 --rounds 1 --generator haiku55

This is a robustness test of OUR checker on public benchmark problems (see docs/methods/redteam.md). It is not an
attack on any deployed tool. All outputs live under <run_dir>/redteam/ and are quarantined: they never enter the
main generations file, the main annotation sheets, or any reported main-run statistic.

Output: data/outputs/<run_id>/redteam/redteam_generations.jsonl (append-only; reruns resume). Then run the full
verifier on that file (python src/verify.py <file>), blind-label with make_blind_sheet, and call
recall_under_attack on the verify rows (+ labels).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from pathlib import Path

import pandas as pd
import yaml

from common import FROZEN, OUTPUTS, append_jsonl, read_jsonl, sha256_text
from deterministic_checks import check
from llm import call_with_one_retry, done_ids, fill, load_prompt, make_provider, parse_json_block
from make_annotation_sheets import LABEL_COLUMNS
from verify import load_sources

PROMPT = "attacker_v1"
SUBDIR = "redteam"
GEN_FILE = "redteam_generations.jsonl"


def _flag_summary(det: dict) -> str:
    return "; ".join(f"{f['code']} ({f['detail']})" for f in det["flags"])


def attack(source: dict, provider, rounds: int = 1) -> dict:
    """Ask the attacker prompt for a subtly leaking rewrite of `source`; return a generation-schema record.

    The record has no output_id / run_id (run_attacks adds them). With rounds > 1 the deterministic layer's flags
    are fed back ("your rewrite was caught for: ...") and another attempt is requested; the last attempt is kept.
    Rounds stop early once an attempt raises no deterministic flag. Each round is one call (one retry on API error).
    """
    system, user_t, prompt_sha = load_prompt(PROMPT)
    user0 = fill(user_t, problem_text=source["text"])
    user, log, usage = user0, [], {"input_tokens": 0, "output_tokens": 0}
    res, parsed = {}, None
    for r in range(1, max(1, rounds) + 1):
        res = call_with_one_retry(provider, system, user)
        raw = res.get("raw_output")
        parsed = parse_json_block(raw) if raw else None
        for k in usage:
            usage[k] += (res.get("usage") or {}).get(k) or 0
        cand = (parsed or {}).get("adapted_problem")
        det = check(source["text"], cand, "redteam") if cand else None
        log.append({"round": r, "raw_output": raw, "det_decision": det and det["decision"],
                    "det_flags": det and [f["code"] for f in det["flags"]]})
        if det is None or not det["flags"] or r == rounds:
            break
        user = (f"{user0}\n\nYour previous attempt was:\n\"{cand}\"\n\nYour rewrite was caught for: {_flag_summary(det)}.\n"
                "Make another attempt that avoids these cues while still leaking subtly. Return only the JSON object.")
    return {
        "generator": f"redteam:{provider.model}", "transformation": "redteam",
        "source_id": source["source_id"], "dataset": source["dataset"], "partition": source["partition"],
        "source_sha256": sha256_text(source["text"]), "prompt_version": PROMPT, "prompt_sha256": prompt_sha,
        **res, "usage": usage,
        "status": "ATTACK", "tactic": (parsed or {}).get("tactic"),
        "adapted_problem": (parsed or {}).get("adapted_problem"),
        "parse_error": bool(res.get("raw_output")) and parsed is None,
        "rounds_used": len(log), "rounds_log": log,
    }


def run_attacks(cfg: dict, run_dir: Path, n_sources: int = 50, mock: bool = False,
                generator_name: str | None = None, rounds: int = 1) -> Path:
    """Attack the first `n_sources` main-partition sources; append to <run_dir>/redteam/redteam_generations.jsonl."""
    out_dir = Path(run_dir) / SUBDIR
    out_path = out_dir / GEN_FILE
    gens = {g["name"]: g for g in cfg["generators"]}
    gen = gens[generator_name] if generator_name else cfg["generators"][0]
    provider = make_provider({"provider": "mock", "model": "mock"} if mock else gen)
    srcs = [r for r in read_jsonl(FROZEN / "main.jsonl") if r.get("text")][:n_sources]
    seen = done_ids(out_path)
    for s in srcs:
        oid = f"{cfg['run_id']}|{SUBDIR}|{gen['name']}|{s['source_id']}"
        if oid in seen:
            continue
        rec = attack(s, provider, rounds)
        append_jsonl(out_path, {"output_id": oid, "run_id": cfg["run_id"], "attacker": gen["name"], **rec})
        print(f"{oid}  {rec['status']}  tactic={rec['tactic']}" + (f"  ERROR {rec['error']}" if rec.get("error") else ""))
    return out_path


def _rate(k: int, n: int) -> float | None:
    return k / n if n else None


def recall_under_attack(verify_rows: list[dict], labels_df: pd.DataFrame | None = None,
                        generations: list[dict] | None = None) -> dict:
    """Share of attack outputs the verifier flags, overall and by tactic.

    verify_rows: rows of verify.py output for the redteam file. `generations` (optional) supplies the tactic by
    output_id; a `tactic` key on the verify row is used if present. Reported rates:
      det_flag_rate     deterministic layer alone, decision != PASS
      full_flag_rate    full verifier, decision != PASS   (the FLAG_ANY operating point)
      full_reject_rate  full verifier, decision == REJECT (the FLAG_REJECT operating point)
    labels_df (human labels with output_id and either leakage_level or SAFE): among confirmed-unsafe attacks
    (leakage_level > 0, else SAFE == 0) the same three rates are reported as *_recall_confirmed.
    """
    tactic_of = {g["output_id"]: g.get("tactic") for g in generations or []}
    rows = []
    for r in verify_rows:
        rows.append({"output_id": r["output_id"], "tactic": tactic_of.get(r["output_id"]) or r.get("tactic"),
                     "det": r["deterministic"]["decision"] != "PASS", "full": r["decision"] != "PASS",
                     "reject": r["decision"] == "REJECT"})
    df = pd.DataFrame(rows, columns=["output_id", "tactic", "det", "full", "reject"])
    out = {"n_attacks": len(df), "det_flag_rate": _rate(int(df["det"].sum()), len(df)),
           "full_flag_rate": _rate(int(df["full"].sum()), len(df)),
           "full_reject_rate": _rate(int(df["reject"].sum()), len(df))}
    if df["tactic"].notna().any():
        out["by_tactic"] = {str(t): {"n": len(g), "det_flag_rate": g["det"].mean(), "full_flag_rate": g["full"].mean(),
                                     "full_reject_rate": g["reject"].mean()}
                            for t, g in df.dropna(subset=["tactic"]).groupby("tactic")}
    if labels_df is not None:
        lab = labels_df.drop_duplicates("output_id")
        if "leakage_level" in lab:
            unsafe = pd.to_numeric(lab["leakage_level"], errors="coerce").fillna(0) > 0
        else:
            unsafe = lab["SAFE"].astype(int) == 0
        conf = df[df["output_id"].isin(set(lab.loc[unsafe, "output_id"]))]
        out.update(n_labeled=int(df["output_id"].isin(set(lab["output_id"])).sum()), n_confirmed_unsafe=len(conf),
                   det_recall_confirmed=_rate(int(conf["det"].sum()), len(conf)),
                   full_recall_confirmed=_rate(int(conf["full"].sum()), len(conf)),
                   reject_recall_confirmed=_rate(int(conf["reject"].sum()), len(conf)))
    return out


def make_blind_sheet(gen_path: Path, out_csv: Path, n: int = 30, seed: int = 2880,
                     main_generations: Path | None = None) -> Path:
    """Blinded sheet: n attack outputs mixed with n non-attack outputs (if the main generations file exists).

    Same columns as make_annotation_sheets. To keep attacks indistinguishable, transformation_requested is "plain"
    for every row, model_status is blank, and non-attack rows are drawn from plain outputs when enough exist.
    A KEY file (annotation_id -> output_id, is_attack, tactic) is written next to the sheet. Both stay in redteam/.
    """
    gen_path, out_csv = Path(gen_path), Path(out_csv)
    if gen_path.parent.resolve() not in out_csv.resolve().parents:
        raise ValueError(f"blind sheet must be written under {gen_path.parent} (quarantine)")
    rng = random.Random(seed)
    attacks = [g for g in read_jsonl(gen_path) if g.get("adapted_problem")]
    attacks = rng.sample(attacks, min(n, len(attacks)))
    main_generations = Path(main_generations) if main_generations else gen_path.parent.parent / "generations.jsonl"
    controls = []
    if main_generations.exists():
        pool = [g for g in read_jsonl(main_generations) if g.get("adapted_problem") and g.get("transformation") != "redteam"]
        plain = [g for g in pool if g.get("transformation") == "plain"]
        pool = plain if len(plain) >= n else pool
        controls = rng.sample(pool, min(n, len(pool)))
    items = [dict(g, is_attack=True) for g in attacks] + [dict(g, is_attack=False) for g in controls]
    src = load_sources()
    for it in items:
        it["annotation_id"] = "a" + hashlib.sha256(f"{seed}|{it['output_id']}".encode()).hexdigest()[:10]
    rng.shuffle(items)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = ["annotation_id", "transformation_requested", "model_status", "original", "adaptation", *LABEL_COLUMNS]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for it in items:
            w.writerow({"annotation_id": it["annotation_id"], "transformation_requested": "plain", "model_status": "",
                        "original": src[it["source_id"]], "adaptation": it["adapted_problem"],
                        **{c: "" for c in LABEL_COLUMNS}})
    with open(out_csv.with_name(out_csv.stem + "_KEY_DO_NOT_OPEN.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["annotation_id", "output_id", "source_id", "generator", "is_attack", "tactic"])
        for it in items:
            w.writerow([it["annotation_id"], it["output_id"], it["source_id"], it["generator"], it["is_attack"],
                        it.get("tactic") or ""])
    return out_csv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--mock", action="store_true", help="offline dry run with the mock provider")
    ap.add_argument("--n", type=int, default=50, help="number of main-partition sources to attack")
    ap.add_argument("--rounds", type=int, default=1, help="attempts per source; >1 feeds back deterministic flags")
    ap.add_argument("--generator", default=None, help="generator name from the config (default: first)")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    if args.mock:  # keep dry runs out of the real run's folders
        cfg["run_id"] += "-mock"
    run_dir = OUTPUTS / cfg["run_id"]
    path = run_attacks(cfg, run_dir, args.n, args.mock, args.generator, args.rounds)

    src = load_sources()
    rows = [g for g in read_jsonl(path) if g.get("adapted_problem")]
    flagged = [g for g in rows if check(src[g["source_id"]], g["adapted_problem"], "redteam")["decision"] != "PASS"]
    print(f"\n{len(rows)} attack outputs; deterministic layer flagged {len(flagged)} "
          f"({len(flagged) / max(1, len(rows)):.1%}); unflagged = candidate evasions for human review")
    print(f"\nNext (full verifier on the quarantined file):\n  python src/verify.py {path} --config {args.config}"
          + (" --mock" if args.mock else ""))
    print("Then: redteam.make_blind_sheet(...) for blind labels, redteam.recall_under_attack(...) for recall.")


if __name__ == "__main__":
    main()
