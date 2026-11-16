"""Dev-pilot health gate + slide-8 summary for a free-tier run (dev problems only; never reads main-study files).

  python scripts/pilot_gate.py --run data/outputs/ollama-v1 --config config.ollama.yaml

Exit code 1 if any stop rule from docs/plan/AGENT_PROMPT_OSCAR.md section 4 fires:
  * more than 5% generation parse errors (overall), or any generation API error;
  * critic replies that aren't valid JSON (any for the primary critic, >5% for a secondary critic);
  * replies cut off at max_tokens (finish_reason "length") in generation, critic or extraction;
  * a model that refuses or returns empty text.
The main-run Slurm job runs this first and stops if it fails.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml


def rows(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()] if p.exists() else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    run, cfg = Path(a.run), yaml.safe_load(open(a.config))
    critics = cfg.get("critics") or [{"name": "critic"}]        # single-critic configs have one `critic:` block
    primary = cfg.get("primary_critic", critics[0]["name"])
    gens = rows(run / "pilot_generations.jsonl")
    fails: list[str] = []
    if not gens:
        print("GATE FAIL: no pilot_generations.jsonl rows")
        return 1

    print(f"== generation ({len(gens)} rows)")
    by_gen = defaultdict(list)
    for g in gens:
        by_gen[g["generator"]].append(g)
    for name, rs in by_gen.items():
        lat = [r["latency_s"] for r in rs if r.get("latency_s") is not None]
        print(f"  {name:<12} n={len(rs)} status={dict(Counter(r.get('status') for r in rs))} "
              f"parse_error={sum(bool(r.get('parse_error')) for r in rs)} error={sum(bool(r.get('error')) for r in rs)} "
              f"stop={dict(Counter(r.get('stop_reason') for r in rs))} think_chars>0={sum((r.get('think_chars') or 0) > 0 for r in rs)} "
              f"out_tok_mean={st.mean([r['usage']['output_tokens'] for r in rs if r.get('usage')] or [0]):.0f} "
              f"latency_mean={st.mean(lat or [0]):.1f}s")
    pe = sum(bool(r.get("parse_error")) for r in gens) / len(gens)
    if pe > 0.05:
        fails.append(f"generation parse errors {pe:.1%} > 5%")
    if any(r.get("error") for r in gens):
        fails.append(f"{sum(bool(r.get('error')) for r in gens)} generation API errors")
    if any(r.get("stop_reason") == "length" for r in gens):
        fails.append(f"{sum(r.get('stop_reason') == 'length' for r in gens)} generations cut off at max_tokens")
    empty = [r["output_id"] for r in gens if not r.get("error") and not (r.get("raw_output") or "").strip()]
    if empty:
        fails.append(f"{len(empty)} empty generations: {empty[:3]}")

    table = {}
    for c in critics:
        name = c["name"]
        suffix = "verify-critic-det-program" if name == primary else f"verify-critic@{name}-det-program"
        vs = rows(run / f"pilot_generations.{suffix}.jsonl")
        if not vs:
            fails.append(f"critic {name}: no verify rows")
            continue
        err = [v for v in vs if (v.get("critic") or {}).get("_error")]
        cut = [v for v in vs if ((v.get("critic") or {}).get("_meta") or {}).get("stop_reason") == "length"]
        lat = [v["critic"]["_meta"]["latency_s"] for v in vs if (v.get("critic") or {}).get("_meta", {}).get("latency_s")]
        print(f"== critic {name}{' (primary)' if name == primary else ''}: n={len(vs)} "
              f"decision={dict(Counter(v['decision'] for v in vs))} overall={dict(Counter((v.get('critic') or {}).get('overall') for v in vs))} "
              f"invalid_json={len(err)} cut_off={len(cut)} latency_mean={st.mean(lat or [0]):.1f}s")
        if (name == primary and err) or len(err) / len(vs) > 0.05:
            fails.append(f"critic {name}: {len(err)} invalid/missing JSON replies")
        if cut:
            fails.append(f"critic {name}: {len(cut)} replies cut off at max_tokens")
        if name == primary:
            gen_of = {g["output_id"]: g["generator"] for g in gens}
            for v in vs:
                t = table.setdefault(gen_of.get(v["output_id"], "?"), Counter())
                t["rewrites"] += 1
                t[v["decision"]] += 1
                t["match"] += (v.get("program") or {}).get("status") == "MATCH"
            prog = Counter((v.get("program") or {}).get("status") for v in vs)
            print(f"   program layer: {dict(prog)}")

    ex = rows(run / "extractions.jsonl")
    ex_lat = [e["meta"]["latency_s"] for e in ex if (e.get("meta") or {}).get("latency_s")]
    ex_cut = sum((e.get("meta") or {}).get("stop_reason") == "length" for e in ex)
    ex_bad = sum(not e.get("extraction") for e in ex)
    print(f"== extractions: n={len(ex)} failed={ex_bad} cut_off={ex_cut} latency_mean={st.mean(ex_lat or [0]):.1f}s")
    if ex_cut:
        fails.append(f"{ex_cut} extractions cut off at max_tokens")

    print("\n| Rewriter | rewrites | pass | review | reject | same answer recomputed |\n|---|---|---|---|---|---|")
    for g, t in table.items():
        print(f"| {g} | {t['rewrites']} | {t['PASS']} | {t['REVIEW']} | {t['REJECT']} | {t['match']}/{t['rewrites']} |")

    print("\nGATE " + ("FAIL:\n  - " + "\n  - ".join(fails) if fails else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
