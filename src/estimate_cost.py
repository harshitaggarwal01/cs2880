"""Estimate the API cost of a run before spending anything (no network, no keys).

  python src/estimate_cost.py --config config.matrix.yaml                 # main run, per step and per model
  python src/estimate_cost.py --config config.matrix-budget.yaml --cap 9  # does it fit a $9 budget?
  python src/estimate_cost.py --config config.matrix.yaml --pilot         # the 10-problem dev pilot only

How the estimate is built
  counts   sources per partition come from data/frozen/ (GSM1K counts its frozen ids, whose text is fetched at run
           time); outputs = generators x (sources x transformations + realistic-prompt problems); repairs = an
           assumed share of outputs (default 0.275, the dev-pilot REVIEW+REJECT rate under checker v1.1); the primary
           critic and the extractor also see the repairs; extraction is cached per distinct text, so each source is
           extracted once.
  tokens   per call, from the Nov 2 real-pilot ledger (data/outputs/anthropic-v1/ledger.csv) when present, otherwise
           built-in defaults of the same size; realistic-prompt replies are free text and assumed longer.
  prices   the config's `prices:` table (USD per 1M tokens). OpenRouter prices there are conservative upper bounds,
           so the estimate is an upper bound for Qwen calls; the ledger later records host-reported costs.
The orchestrator uses `step_estimates` for its spending guard (`budget_usd` in the config; see run_phase1.py).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from common import FROZEN, OUTPUTS, read_jsonl

DEFAULT_TOKENS = {  # stage -> (input, output) tokens per call
    "gen": (545, 180), "gen_naive": (560, 420), "critic": (1120, 510), "critic_naive": (1350, 560),
    "extract": (480, 550), "repair": (1300, 260),
}
REPAIR_RATE = 0.275
VARIANCE_SOURCES = 20


def measured_tokens(ledger_csv: Path = OUTPUTS / "anthropic-v1" / "ledger.csv") -> dict[str, tuple[float, float]]:
    """Mean tokens per call by stage from a real ledger; missing stages keep the defaults."""
    tok = dict(DEFAULT_TOKENS)
    if ledger_csv.exists():
        led = pd.read_csv(ledger_csv)
        for stage in ("critic", "extract", "repair"):
            d = led[led["stage"] == stage]
            if len(d):
                tok[stage] = (float(d["input_tokens"].mean()), float(d["output_tokens"].mean()))
        g = led[led["stage"] == "gen"]
        if len(g):
            tok["gen"] = (float(g["input_tokens"].mean()), float(g["output_tokens"].mean()))
    return tok


def n_sources(partitions: list[str]) -> dict[str, int]:
    out = {}
    for part in partitions:
        path = FROZEN / ("ext_gsm1k_ids.jsonl" if part == "ext_gsm1k" else f"{part}.jsonl")
        if part == "ext_gsm1k" and (FROZEN / "ext_gsm1k.jsonl").exists():
            path = FROZEN / "ext_gsm1k.jsonl"
        out[part] = len(read_jsonl(path)) if path.exists() else 0
    return out


def price(cfg: dict, model: str) -> tuple[float, float]:
    p = (cfg.get("prices") or {}).get(model)
    if not p:
        raise KeyError(f"no price for {model!r} in the config's prices: table")
    return float(p["in"]), float(p["out"])


def usd(cfg: dict, model: str, calls: float, tokens: tuple[float, float]) -> float:
    pin, pout = price(cfg, model)
    return calls * (tokens[0] * pin + tokens[1] * pout) / 1e6


def critic_list(cfg: dict) -> tuple[list[dict], str]:
    if cfg.get("critics"):
        return cfg["critics"], cfg["primary_critic"]
    c = {**cfg["critic"], "name": cfg["critic"].get("name", "primary")}
    return [c], c["name"]


def estimate(cfg: dict, pilot: bool = False, repair_rate: float = REPAIR_RATE, variance: bool = True,
             tokens: dict | None = None) -> pd.DataFrame:
    """One row per (step, model): calls, tokens and USD. Steps match run_phase1 step names."""
    tok = tokens or measured_tokens()
    gens, tfs = cfg["generators"], list(cfg["transformations"])
    critics, primary = critic_list(cfg)
    extractor = cfg["extractor"]["model"]
    if pilot:
        src = n_sources(["dev"])
        n_src, naive_n = src["dev"], 0
    else:
        src = n_sources(cfg["partitions"])
        n_src = sum(src.values())
        ab = cfg.get("ablation") or {}
        naive_n = min(int(ab.get("first_n", 0)), src.get(ab.get("partition", "main"), 0)) if ab else 0
    rows = []

    def add(step, model, calls, kind):
        rows.append({"step": step, "model": model, "calls": round(calls, 1), "input_tokens": round(calls * tok[kind][0]),
                     "output_tokens": round(calls * tok[kind][1]), "usd": usd(cfg, model, calls, tok[kind])})

    careful = n_src * len(tfs)
    step_gen = "pilot" if pilot else "generate"
    for g in gens:
        add(step_gen, g["model"], careful, "gen")
        if naive_n:
            add("ablation", g["model"], naive_n, "gen_naive")
    outputs_careful = len(gens) * careful
    outputs_naive = len(gens) * naive_n
    outputs = outputs_careful + outputs_naive
    repairs = 0 if pilot else repair_rate * outputs
    step_verify = "pilot_verify" if pilot else "verify"
    for c in critics:
        step = step_verify if c["name"] == primary else ("pilot_verify" if pilot else "critics")
        add(step, c["model"], outputs_careful, "critic")
        if outputs_naive:
            add(step, c["model"], outputs_naive, "critic_naive")
    add(step_verify, extractor, outputs + n_src, "extract")
    if repairs:
        share = {g["name"]: 1 / len(gens) for g in gens}
        for g in gens:
            add("repair", g["model"], repairs * share[g["name"]], "repair")
        add("verify_repairs", next(c["model"] for c in critics if c["name"] == primary), repairs, "critic")
        add("verify_repairs", extractor, repairs, "extract")
    if variance and not pilot:
        n_var = min(VARIANCE_SOURCES, src.get("main", 0))
        for g in gens:
            add("variance", g["model"], n_var * len(tfs), "gen")
            if naive_n:
                add("variance", g["model"], n_var, "gen_naive")
        n_var_out = len(gens) * n_var * (len(tfs) + (1 if naive_n else 0))
        add("variance", next(c["model"] for c in critics if c["name"] == primary), n_var_out, "critic")
        add("variance", extractor, n_var_out, "extract")
    return pd.DataFrame(rows)


def step_estimates(cfg: dict, **kw) -> dict[str, float]:
    t = estimate(cfg, **kw)
    return t.groupby("step")["usd"].sum().to_dict()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--pilot", action="store_true", help="estimate the 10-problem dev pilot only")
    ap.add_argument("--repair-rate", type=float, default=REPAIR_RATE)
    ap.add_argument("--no-variance", action="store_true")
    ap.add_argument("--cap", type=float, help="budget in USD to compare against")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    t = estimate(cfg, pilot=args.pilot, repair_rate=args.repair_rate, variance=not args.no_variance)
    by_step = t.groupby("step")["usd"].sum().round(2)
    by_model = t.groupby("model")["usd"].sum().round(2)
    total = float(t["usd"].sum())
    print(f"# Cost estimate: {args.config}{' (dev pilot)' if args.pilot else ''}\n")
    print(t.assign(usd=t["usd"].round(3)).to_string(index=False), "\n")
    print("By step:\n" + by_step.to_string(), "\n")
    print("By model:\n" + by_model.to_string(), "\n")
    print(f"TOTAL ~ ${total:.2f} (upper bound for OpenRouter models; actual from the ledger after the run)")
    if args.cap is not None:
        print(f"cap ${args.cap:.2f}: {'fits' if total <= args.cap else 'DOES NOT FIT'} "
              f"(margin ${args.cap - total:+.2f})")


if __name__ == "__main__":
    main()
