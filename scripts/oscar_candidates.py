"""Screen cheap rewriter candidates on the 10 DEV problems with the real plain_v1/chunked_v1 prompts.

Reports, per model x style: parse success (the pipeline's own parse_json_block), status counts, empty replies,
think_chars and mean latency. Writes raw rows to data/outputs/<run_id>/candidates/ (dev only; not study data).
  python scripts/oscar_candidates.py config.ollama.yaml phi3:latest mistral:7b gemma3:4b qwen3:4b llama3.2:1b
"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, "src")
from collect_outputs import sources  # noqa: E402
from llm import call_with_one_retry, fill, load_prompt, make_provider, parse_json_block  # noqa: E402

cfg = yaml.safe_load(open(sys.argv[1]))
models = sys.argv[2:]
dev = [s for s in sources(["dev"]) if s["partition"] == "dev"]
out_dir = Path("data/outputs") / cfg["run_id"] / "candidates"
out_dir.mkdir(parents=True, exist_ok=True)
print(f"{len(dev)} dev problems", flush=True)
for model in models:
    settings = {"max_tokens": 2048, "temperature": 0.7, "top_p": 0.9, "seed": 2880}
    if model.startswith("qwen3"):
        settings["extra_body"] = {"reasoning_effort": "none"}
    prov = make_provider({"provider": "openai_compat", "base_url": "http://localhost:11434/v1", "model": model,
                          "settings": settings})
    with open(out_dir / f"{model.replace(':', '_')}.jsonl", "w") as f:
        for tf in ("plain", "chunked"):
            system, user_t, _ = load_prompt(f"{tf}_v1")
            rows = []
            for s in dev:
                r = call_with_one_retry(prov, system, fill(user_t, problem_text=s["text"]))
                p = parse_json_block(r.get("raw_output") or "")
                r.update(source_id=s["source_id"], transformation=tf, parsed_ok=bool(p and p.get("adapted_problem")
                         or (p and p.get("status") == "NO_REWRITE_NEEDED")), status=(p or {}).get("status"))
                rows.append(r)
                f.write(json.dumps(r) + "\n")
            lat = [r["latency_s"] for r in rows[1:] if r.get("latency_s")]  # skip the cold-load call
            print(f"{model:<13} {tf:<8} parsed={sum(r['parsed_ok'] for r in rows)}/{len(rows)} "
                  f"status={dict(Counter(r['status'] for r in rows))} empty={sum(not (r.get('raw_output') or '').strip() for r in rows)} "
                  f"errors={sum(bool(r.get('error')) for r in rows)} cut={sum(r.get('stop_reason') == 'length' for r in rows)} "
                  f"think>0={sum((r.get('think_chars') or 0) > 0 for r in rows)} warm_latency={st.mean(lat or [0]):.1f}s", flush=True)
