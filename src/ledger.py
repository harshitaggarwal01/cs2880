"""Cost and latency ledger for a run: one row per billable model call.

  python src/ledger.py --run data/outputs/main-v1 --config config.yaml

Scans the run folder (generations, ablation, pilot, baseline, verify critic calls, cached extractions,
repairs, variance reruns), writes <run>/ledger.csv and prints a summary as a markdown table.
Cost = input tokens x "in" price + (output + thinking tokens) x "out" price, USD per 1M tokens.
Derived verify rows (subset layers computed offline) are skipped, and each extracted text is counted once.
When a call carries a host-reported cost (OpenRouter `usage.cost` -> `reported_cost_usd`), that is used instead of
the price table (`cost_source` = "reported" vs "price_table"). `critic_name` and `family` (the model family of the
generator, critic or extractor that made the call) support the generator x critic matrix.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from common import read_jsonl

COLUMNS = ["output_id", "stage", "generator", "transformation", "partition", "model", "critic_name", "family",
           "input_tokens", "output_tokens", "thinking_tokens", "usd", "cost_source", "latency_s", "timestamp"]
GEN_FILES = ["generations.jsonl", "ablation_generations.jsonl", "pilot_generations.jsonl", "baseline.jsonl"]


def price_call(usage: dict | None, model: str | None, prices: dict) -> float:
    """USD for one call; model matched exactly, else by longest price key that is a prefix, else free."""
    key = model if model in prices else max((k for k in prices if model and model.startswith(k)), key=len, default=None)
    if key is None:
        return 0.0
    u = usage or {}
    tokens_in = u.get("input_tokens") or 0
    tokens_out = (u.get("output_tokens") or 0) + (u.get("thinking_tokens") or 0)
    return tokens_in * prices[key]["in"] / 1e6 + tokens_out * prices[key]["out"] / 1e6


def _row(output_id: str, stage: str, ctx: dict, model: str | None, usage: dict | None, latency, ts, prices: dict,
         reported: float | None = None, critic_name: str | None = None, family: str | None = None) -> dict:
    u = usage or {}
    return {"output_id": output_id, "stage": stage, "generator": ctx.get("generator"),
            "transformation": ctx.get("transformation"), "partition": ctx.get("partition"), "model": model,
            "critic_name": critic_name, "family": family,
            "input_tokens": u.get("input_tokens") or 0, "output_tokens": u.get("output_tokens") or 0,
            "thinking_tokens": u.get("thinking_tokens") or 0,
            "usd": float(reported) if reported is not None else price_call(u, model, prices),
            "cost_source": "reported" if reported is not None else "price_table",
            "latency_s": latency or 0.0, "timestamp": ts}


def families(cfg: dict) -> tuple[dict[str, str], dict[str, dict]]:
    """generator name -> family, and critic name -> spec (legacy single `critic:` becomes one entry)."""
    gen_fam = {g["name"]: g.get("family") for g in cfg.get("generators", [])}
    if cfg.get("critics"):
        crit = {c["name"]: c for c in cfg["critics"]}
    elif cfg.get("critic"):
        crit = {cfg["critic"].get("name", "primary"): cfg["critic"]}
    else:
        crit = {}
    return gen_fam, crit


def build_ledger(run_dir: Path, cfg: dict) -> pd.DataFrame:
    prices = cfg.get("prices", {})
    gen_fam, crit_specs = families(cfg)
    rows: list[dict] = []
    ctx: dict[str, dict] = {}  # output_id -> generator/transformation/partition, for verify and variance rows

    def load(path: Path) -> list[dict]:
        return read_jsonl(path) if path.exists() else []

    for name in GEN_FILES + ["repairs.jsonl"]:
        stage = "repair" if name == "repairs.jsonl" else "gen"
        for g in load(run_dir / name):
            ctx[g["output_id"]] = g
            model = g.get("returned_model") or g.get("requested_model")
            rows.append(_row(g["output_id"], stage, g, model, g.get("usage"), g.get("latency_s"), g.get("timestamp"),
                             prices, g.get("reported_cost_usd"), family=gen_fam.get(g.get("generator"))))

    seen_texts: set[str] = set()
    legacy = next(iter(crit_specs.values()), {})
    critic_model = legacy.get("model")
    extract_model = (cfg.get("extractor") or {}).get("model")
    extract_fam = (cfg.get("extractor") or {}).get("family")
    for path in sorted(run_dir.glob("*.verify-*.jsonl")):
        for v in read_jsonl(path):
            if v.get("derived_from"):
                continue
            oid, c = v["output_id"], ctx.get(v["output_id"], {})
            meta = (v.get("critic") or {}).get("_meta")
            if meta:
                cname = v.get("critic_name") or next(iter(crit_specs), None)
                spec = crit_specs.get(cname, {})
                rows.append(_row(oid, "critic", c, meta.get("returned_model") or v.get("critic_model")
                                 or spec.get("model") or critic_model, meta.get("usage"), meta.get("latency_s"),
                                 v.get("timestamp"), prices, meta.get("reported_cost_usd"), cname,
                                 v.get("critic_family") or spec.get("family")))
            for m in (v.get("extract_meta") or {}).values():
                if m.get("text_sha256") in seen_texts:
                    continue
                seen_texts.add(m.get("text_sha256"))
                rows.append(_row(oid, "extract", c, m.get("returned_model") or extract_model, m.get("usage"),
                                 m.get("latency_s"), v.get("timestamp"), prices, m.get("reported_cost_usd"),
                                 family=extract_fam))

    for e in load(run_dir / "extractions.jsonl"):  # paid for but never attached to a verify row (e.g. crashed run)
        if e["key"] not in seen_texts:
            m = e.get("meta") or {}
            rows.append(_row("", "extract", {}, m.get("returned_model") or extract_model, m.get("usage"),
                             m.get("latency_s"), None, prices, m.get("reported_cost_usd"), family=extract_fam))

    for path in sorted((run_dir / "variance").glob("*.jsonl")):
        for r in read_jsonl(path):
            oid = r.get("output_id") or r.get("source_output_id") or ""
            c = {**ctx.get(oid, {}), **{k: r[k] for k in ("generator", "transformation", "partition") if k in r}}
            model = r.get("returned_model") or r.get("requested_model") or r.get("model")
            rows.append(_row(oid, "variance", c, model, r.get("usage"), r.get("latency_s"), r.get("timestamp"), prices))

    ledger = pd.DataFrame(rows, columns=COLUMNS)
    ledger.to_csv(run_dir / "ledger.csv", index=False)
    return ledger


def summarize(ledger: pd.DataFrame) -> pd.DataFrame:
    """Totals by stage and by (generator, transformation), plus a grand total."""
    agg = {"calls": ("output_id", "size"), "input_tokens": ("input_tokens", "sum"),
           "output_tokens": ("output_tokens", "sum"), "thinking_tokens": ("thinking_tokens", "sum"),
           "usd": ("usd", "sum"), "mean_latency_s": ("latency_s", "mean")}
    parts = []
    if len(ledger):
        by_stage = ledger.groupby("stage").agg(**agg).reset_index().rename(columns={"stage": "key"})
        by_stage.insert(0, "group", "stage")
        by_gt = ledger.assign(key=ledger["generator"].fillna("-") + " / " + ledger["transformation"].fillna("-"))
        by_gt = by_gt.groupby("key").agg(**agg).reset_index()
        by_gt.insert(0, "group", "generator / transformation")
        parts = [by_stage, by_gt]
    total = pd.DataFrame([{"group": "total", "key": "all", "calls": len(ledger),
                           "input_tokens": ledger["input_tokens"].sum(), "output_tokens": ledger["output_tokens"].sum(),
                           "thinking_tokens": ledger["thinking_tokens"].sum(), "usd": ledger["usd"].sum(),
                           "mean_latency_s": ledger["latency_s"].mean() if len(ledger) else 0.0}])
    return pd.concat([*parts, total], ignore_index=True)


def per_item_cost(ledger: pd.DataFrame) -> dict[str, float]:
    """USD per original output_id over gen + critic + extract + repair (repair rows fold into the original)."""
    sub = ledger[ledger["stage"].isin(["gen", "critic", "extract", "repair"]) & (ledger["output_id"] != "")]
    keys = sub["output_id"].str.replace(r"\|repair\d+$", "", regex=True)
    return sub["usd"].groupby(keys).sum().to_dict()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run folder, e.g. data/outputs/main-v1")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    run_dir = Path(args.run)
    ledger = build_ledger(run_dir, yaml.safe_load(open(args.config)))
    print(summarize(ledger).to_markdown(index=False, floatfmt=".4f"))
    print(f"\n{len(ledger)} calls -> {run_dir / 'ledger.csv'}")


if __name__ == "__main__":
    main()
