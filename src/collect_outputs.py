"""Generate adaptations for every (source x generator x transformation) and log them immutably.

  python src/collect_outputs.py --config config.yaml                 # full primary run
  python src/collect_outputs.py --config config.yaml --pilot          # 10 dev problems only
  python src/collect_outputs.py --config config.yaml --ablation       # naive-prompt ablation
  python src/collect_outputs.py --config config.example.yaml --mock   # offline dry run

Output: data/outputs/<run_id>/generations.jsonl (append-only; reruns resume and
never overwrite). The first returned response is kept; the only retry is one
retry on a technical/API error. Never regenerate because an output looks bad.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from common import FROZEN, OUTPUTS, append_jsonl, read_jsonl, sha256_text
from llm import call_with_one_retry, done_ids, fill, load_prompt, make_provider, parse_json_block


def sources(partitions: list[str]) -> list[dict]:
    rows = []
    for part in partitions:
        path = FROZEN / ("ext_gsm1k.jsonl" if part == "ext_gsm1k" else f"{part}.jsonl")
        if not path.exists():
            print(f"skip {part}: {path.name} missing (for GSM1K run: python src/fetch_data.py --gsm1k)")
            continue
        rows += [r for r in read_jsonl(path) if r.get("text")]
    return rows


def run(cfg: dict, srcs: list[dict], transformations: list[str], out_path: Path, mock: bool) -> None:
    seen = done_ids(out_path)
    total_in = total_out = 0
    for gen in cfg["generators"]:
        provider = make_provider({"provider": "mock", "model": "mock"} if mock else gen)
        for tf in transformations:
            system, user_t, prompt_sha = load_prompt(f"{tf}_v1")
            for s in srcs:
                oid = f"{cfg['run_id']}|{gen['name']}|{tf}|{s['source_id']}"
                if oid in seen:
                    continue
                res = call_with_one_retry(provider, system, fill(user_t, problem_text=s["text"]))
                raw = res.get("raw_output")
                parsed = parse_json_block(raw) if (raw and tf != "naive") else None
                rec = {
                    "output_id": oid, "run_id": cfg["run_id"], "generator": gen["name"], "transformation": tf,
                    "source_id": s["source_id"], "dataset": s["dataset"], "partition": s["partition"],
                    "source_sha256": sha256_text(s["text"]), "prompt_version": f"{tf}_v1", "prompt_sha256": prompt_sha,
                    **res,
                    "status": (parsed or {}).get("status") if tf != "naive" else "FREE_TEXT",
                    "adapted_problem": (parsed or {}).get("adapted_problem") if tf != "naive" else raw,
                    "parse_error": bool(raw) and tf != "naive" and parsed is None,
                }
                append_jsonl(out_path, rec)
                u = res.get("usage") or {}
                total_in += u.get("input_tokens") or 0
                total_out += u.get("output_tokens") or 0
                print(f"{oid}  {rec['status']}  {res.get('latency_s')}s" + (f"  ERROR {res['error']}" if res.get("error") else ""))
    print(f"tokens this session: in={total_in} out={total_out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--pilot", action="store_true", help="dev partition only")
    ap.add_argument("--ablation", action="store_true", help="naive-prompt ablation on the first N main problems")
    ap.add_argument("--mock", action="store_true", help="offline dry run with the mock provider")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    if args.mock:  # keep dry runs out of the real run's output and annotation folders
        cfg["run_id"] += "-mock"
    run_dir = OUTPUTS / cfg["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.frozen.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))

    if args.pilot:
        run(cfg, sources(["dev"]), cfg["transformations"], run_dir / "pilot_generations.jsonl", args.mock)
    elif args.ablation:
        ab = cfg["ablation"]
        run(cfg, sources([ab["partition"]])[: ab["first_n"]], [ab["transformation"]],
            run_dir / "ablation_generations.jsonl", args.mock)
    else:
        run(cfg, sources(cfg["partitions"]), cfg["transformations"], run_dir / "generations.jsonl", args.mock)


if __name__ == "__main__":
    main()
