"""One constrained repair pass for outputs the verifier flagged (REVIEW or REJECT).

  python src/repair.py data/outputs/main-v1/generations.jsonl \
      data/outputs/main-v1/generations.verify-critic-det-program.jsonl --config config.yaml

The repair is done by the SAME generator that produced the output, with the
verifier's concerns as feedback and without the reference solution. Exactly
one attempt; repaired outputs are re-verified and then human-annotated like
first-pass outputs (blind to whether they were repaired).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from common import append_jsonl, read_jsonl
from llm import call_with_one_retry, done_ids, fill, load_prompt, make_provider, parse_json_block
from verify import load_sources


def concerns(v: dict) -> str:
    lines = [f"- {f['code']}: {f['detail']}" for f in v["deterministic"]["flags"]]
    c = v.get("critic") or {}
    for e in c.get("evidence") or []:
        lines.append(f"- {e.get('issue')} (original: \"{e.get('original')}\"; adaptation: \"{e.get('adaptation')}\")")
    if (v.get("program") or {}).get("status") == "MISMATCH":
        lines.append("- The adaptation appears to describe a different calculation than the original.")
    return "\n".join(lines) or "- Unspecified concern; check every quantity, relation, condition and the question."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("generations")
    ap.add_argument("verification")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    gens = {g["output_id"]: g for g in read_jsonl(Path(args.generations))}
    src = load_sources()
    out_path = Path(args.generations).with_name("repairs.jsonl")
    seen = done_ids(out_path)
    system, user_t, sha = load_prompt("repair_v1")
    providers = {g["name"]: make_provider({"provider": "mock", "model": "mock"} if args.mock else g)
                 for g in cfg["generators"]}
    for v in read_jsonl(Path(args.verification)):
        rid = v["output_id"] + "|repair1"
        if v["decision"] == "PASS" or rid in seen:
            continue
        g = gens[v["output_id"]]
        r = call_with_one_retry(providers[g["generator"]], system,
                                fill(user_t, problem_text=src[g["source_id"]], candidate_text=g["adapted_problem"],
                                     transformation=g["transformation"], concerns=concerns(v)))
        parsed = parse_json_block(r.get("raw_output") or "") or {}
        append_jsonl(out_path, {**{k: g[k] for k in ("run_id", "generator", "transformation", "source_id", "dataset",
                                                     "partition", "source_sha256")},
                                "output_id": rid, "repair_of": v["output_id"], "prompt_version": "repair_v1",
                                "prompt_sha256": sha, "verifier_decision_before": v["decision"], **r,
                                "adapted_problem": parsed.get("adapted_problem"), "changes": parsed.get("changes"),
                                "parse_error": parsed == {}})
        print(rid, "repaired" if parsed else "PARSE_ERROR")


if __name__ == "__main__":
    main()
