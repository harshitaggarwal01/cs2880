"""Smoke test for the free tier: one real JSON call per model in the config, plus a thinking on/off probe for Qwen.

Run on a GPU node with the Ollama server up (scripts/oscar_smoke.sbatch). Prints one line per spec.
"""
import json
import sys

import yaml

sys.path.insert(0, "src")
from llm import call_with_one_retry, make_provider  # noqa: E402

cfg = yaml.safe_load(open(sys.argv[1] if len(sys.argv) > 1 else "config.ollama.yaml"))
schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
specs = cfg["generators"] + cfg["critics"] + [dict(cfg["extractor"], name="extractor")]
for s in specs:
    r = call_with_one_retry(make_provider(s), 'Reply with JSON {"ok": true}.', "ping", schema)
    print(f"{s['name']:<14} {s['model']:<12}", r.get("error") or
          dict(json_mode=r.get("json_mode"), schema_valid=r.get("schema_valid"), think_chars=r.get("think_chars"),
               out_tokens=r["usage"]["output_tokens"], stop=r.get("stop_reason"), latency_s=r.get("latency_s")),
          flush=True)

# Does reasoning_effort "none" really switch Qwen3 thinking off on this Ollama? Compare output tokens and the
# separate `reasoning` field Ollama may return outside <think> tags.
from openai import OpenAI  # noqa: E402

cli = OpenAI(base_url="http://localhost:11434/v1", api_key="x", max_retries=0)
q = "A shop sells 3 pens for $2. How much do 12 pens cost? Answer with the number only."
for model in sorted({s["model"] for s in specs if s["model"].startswith("qwen3")}):
    for label, extra in (("default", {}), ("effort=none", {"reasoning_effort": "none"})):
        r = cli.chat.completions.create(model=model, messages=[{"role": "user", "content": q}], max_tokens=2048,
                                        temperature=0, seed=2880, extra_body=extra)
        m = r.choices[0].message
        reasoning = (getattr(m, "model_extra", None) or {}).get("reasoning") or ""
        print(f"THINK-PROBE {model:<10} {label:<12} out_tokens={r.usage.completion_tokens:<5} "
              f"reasoning_field_chars={len(reasoning):<5} think_tag={'<think>' in (m.content or '')} "
              f"content={json.dumps((m.content or '')[-40:])}", flush=True)
