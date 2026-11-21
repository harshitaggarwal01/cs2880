"""Label-free aggregate tables for the main run (no human labels; counts only, no text).

  python scripts/labelfree_summary.py [--run data/outputs/ollama-v1]
  -> analysis/judges_labelfree.csv, analysis/flags_labelfree.csv, analysis/judge_overlap.csv

Judges: every generations.verify-critic*-det-program.jsonl (primary critic = no @suffix). Careful = plain + chunked;
realistic = naive (ablation_generations). Paid spend = sum of reported_cost_usd over every verify file of that critic
(including the pilot), so it matches the paid-critic log total.
"""
import argparse
import collections
import itertools
import json
from pathlib import Path

import pandas as pd

NAMES = {"": "qwen_big_c", "@gemma_c": "gemma_c", "@llama_small_c": "llama_small_c", "@haiku55c": "haiku55c",
         "@sonnet55c": "sonnet55c", "@luna6c": "luna6c", "@sol61c": "sol61c"}


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open()] if path.exists() else []


def transformation(r: dict) -> str:
    return r["output_id"].split("|")[2]


def main(run: Path) -> None:
    out = run / "analysis"
    judges, flagged = [], {}
    for suf, name in NAMES.items():
        gen = rows(run / f"generations.verify-critic{suf}-det-program.jsonl")
        abl = rows(run / f"ablation_generations.verify-critic{suf}-det-program.jsonl")
        careful = [r for r in gen if transformation(r) != "naive"]
        real = [r for r in abl if transformation(r) == "naive"]
        uns = lambda r: (r.get("critic") or {}).get("overall") == "UNSAFE"  # noqa: E731
        mism = [r for r in careful if (r.get("program") or {}).get("status") == "MISMATCH"]
        rej = [r for r in careful if r["deterministic"]["decision"] == "REJECT" or (r.get("program") or {}).get("status") == "MISMATCH"]
        leak = [r for r in careful if any(f["code"].startswith("LEAK") for f in r["deterministic"]["flags"])]
        spend = sum(((r.get("critic") or {}).get("_meta") or {}).get("reported_cost_usd") or 0
                    for f in ("generations", "ablation_generations", "pilot_generations", "repairs")
                    for r in rows(run / f"{f}.verify-critic{suf}-det-program.jsonl"))
        flagged[name] = {r["output_id"] for r in careful if uns(r)}
        judges.append({"critic": name, "careful_n": len(careful), "careful_unsafe": sum(map(uns, careful)),
                       "careful_unsafe_rate": round(sum(map(uns, careful)) / max(len(careful), 1), 4),
                       "answer_mismatch_n": len(mism), "caught_of_mismatch": sum(map(uns, mism)),
                       "rules_or_recompute_reject_n": len(rej), "caught_of_reject": sum(map(uns, rej)),
                       "any_leak_flag_n": len(leak), "caught_of_leak": sum(map(uns, leak)),
                       "realistic_n": len(real), "realistic_unsafe": sum(map(uns, real)),
                       "careful_no_verdict": sum(1 for r in careful if not (r.get("critic") or {}).get("overall")),
                       "verifier_reject_careful": sum(1 for r in careful if r["decision"] == "REJECT"),
                       "paid_spend_usd_incl_pilot": round(spend, 2)})
    pd.DataFrame(judges).to_csv(out / "judges_labelfree.csv", index=False)
    ov = [{"critic_a": a, "critic_b": b, "flagged_a": len(flagged[a]), "flagged_b": len(flagged[b]),
           "both": len(flagged[a] & flagged[b])} for a, b in itertools.combinations(flagged, 2)]
    pd.DataFrame(ov).to_csv(out / "judge_overlap.csv", index=False)
    prim = rows(run / "generations.verify-critic-det-program.jsonl") + rows(run / "ablation_generations.verify-critic-det-program.jsonl")
    cnt = collections.Counter()
    for r in prim:
        stratum = "realistic" if transformation(r) == "naive" else "careful"
        for code in {f["code"] for f in r["deterministic"]["flags"]}:
            cnt[(stratum, code)] += 1
    pd.DataFrame([{"stratum": s, "flag": c, "n_outputs": n} for (s, c), n in sorted(cnt.items())]).to_csv(
        out / "flags_labelfree.csv", index=False)
    print(pd.DataFrame(judges).to_string(index=False))
    print(f"wrote {out}/judges_labelfree.csv, judge_overlap.csv, flags_labelfree.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="data/outputs/ollama-v1")
    main(Path(ap.parse_args().run))
