"""Run the OpenRouter critics of config.ollama-paid.yaml on existing ollama-v1 rewrites, under a hard USD cap.

  python scripts/paid_critics.py --stage pilot   # the 50 dev-pilot rewrites (~$0.5); run this first
  python scripts/paid_critics.py --stage main    # main + ablation rewrites; needs the pilot files (cost per row)

Critics run cheapest first. Before each (critic, file) the script projects its cost from that critic's measured
cost per row on the dev pilot (main stage) or from list prices at 3x the observed local-critic token counts (pilot
stage), and skips it when spent + projected would pass the cap. Spend is the host-reported cost (OpenRouter
usage.cost) when present, else tokens x config prices. verify.py resumes per row, so a rerun never pays twice.
No extraction calls: the program layer reuses <run>/extractions.jsonl (keyed by text) from the GPU job; a text
missing from the cache fails (no local server in a CPU job) and is logged as a failed extraction, never paid for.
The main stage therefore waits for the GPU job's verify step (<run>/.done/verify).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = {"pilot": ["pilot_generations.jsonl"], "main": ["generations.jsonl", "ablation_generations.jsonl"]}
PILOT_TOKENS = (3 * 700, 3 * 300)   # conservative per-row (in, out) before any paid row exists


def rows(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()] if p.exists() else []


def row_cost(v: dict, prices: dict) -> float:
    meta = (v.get("critic") or {}).get("_meta") or {}
    if meta.get("reported_cost_usd") is not None:
        return float(meta["reported_cost_usd"])
    u, p = meta.get("usage") or {}, prices.get(v.get("critic_model"), {"in": 0, "out": 0})
    return (u.get("input_tokens", 0) * p["in"] + u.get("output_tokens", 0) * p["out"]) / 1e6


def out_path(run: Path, gens: str, critic: str) -> Path:
    return run / f"{Path(gens).stem}.verify-critic@{critic}-det-program.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=FILES, required=True)
    ap.add_argument("--config", default="config.ollama-paid.yaml")
    ap.add_argument("--run", default="data/outputs/ollama-v1")
    ap.add_argument("--cap", type=float, help="USD (default: budget_usd in the config)")
    ap.add_argument("--critics", help="comma-separated subset to run (default: all paid critics); parallel jobs each check the shared cap")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(ROOT / a.config))
    run, cap, prices = ROOT / a.run, a.cap if a.cap is not None else float(cfg["budget_usd"]), cfg["prices"]
    paid = [c for c in cfg["critics"] if "openrouter.ai" in (c.get("base_url") or "")]
    paid.sort(key=lambda c: prices[c["model"]]["out"])          # cheapest first
    only = set(a.critics.split(",")) if a.critics else None
    run_list = [c for c in paid if only is None or c["name"] in only]

    def spent() -> float:
        return sum(row_cost(v, prices) for c in paid for f in sum(FILES.values(), [])
                   for v in rows(out_path(run, f, c["name"])))

    missing = sorted({c["api_key_env"] for c in paid if not os.environ.get(c["api_key_env"])})
    if missing:
        print(f"FATAL: {missing} not set (source ~/.config/safeadapt/openrouter.env); nothing was called")
        return 2
    if a.stage == "main" and not (run / ".done" / "verify").exists():
        print("WAIT: the GPU job has not finished its verify step (no .done/verify), so extractions are incomplete")
        return 3
    skipped = []
    for c in run_list:
        pilot_rows = rows(out_path(run, "pilot_generations.jsonl", c["name"]))
        if a.stage == "main":
            if not pilot_rows:
                print(f"SKIP {c['name']}: no dev-pilot rows yet (run --stage pilot first)")
                skipped.append(c["name"])
                continue
            per_row = 1.25 * sum(row_cost(v, prices) for v in pilot_rows) / len(pilot_rows)   # 25% margin
        else:
            p = prices[c["model"]]
            per_row = (PILOT_TOKENS[0] * p["in"] + PILOT_TOKENS[1] * p["out"]) / 1e6
        for f in FILES[a.stage]:
            gens = run / f
            todo = len([g for g in rows(gens) if g.get("adapted_problem")]) - len(rows(out_path(run, f, c["name"])))
            if todo <= 0:
                continue
            now, proj = spent(), per_row * todo
            if now + proj > cap:
                print(f"SKIP {c['name']} on {f}: spent ${now:.2f} + projected ${proj:.2f} > cap ${cap:.2f}")
                skipped.append(c["name"])
                continue
            print(f"RUN  {c['name']} on {f}: {todo} rows, projected ${proj:.2f} (spent so far ${now:.2f})", flush=True)
            r = subprocess.run([sys.executable, "src/verify.py", str(gens), "--config", a.config, "--critic", c["name"]],
                               cwd=ROOT)
            if r.returncode:
                print(f"FAIL {c['name']} on {f}: verify.py exit {r.returncode}; stopping")
                return 1
            vs = rows(out_path(run, f, c["name"]))
            bad = sum(bool((v.get("critic") or {}).get("_error")) for v in vs)
            if bad > 0.05 * max(len(vs), 1):
                print(f"FAIL {c['name']} on {f}: {bad}/{len(vs)} critic errors, e.g. "
                      f"{next(v['critic']['_error'] for v in vs if (v.get('critic') or {}).get('_error'))[:200]!r}; stopping")
                return 1
    print(f"TOTAL paid-critic spend: ${spent():.2f} of ${cap:.2f} cap" + (f"; skipped {skipped}" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
