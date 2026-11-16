#!/bin/bash
# Throughput check for the primary critic/extractor (qwen3:32b): Ollama's native timings (load / prompt / generate),
# flash attention on vs off, on the real extract_v1 prompt for one dev problem. ~5-10 min.
#SBATCH -J safeadapt-bench
#SBATCH -p gpu-debug
#SBATCH --qos=gpu-debug
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a40|a6000
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH -t 00:30:00
#SBATCH -o logs/bench-%j.out
set -euo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate
for FA in 1 0; do
  echo "== OLLAMA_FLASH_ATTENTION=$FA"
  source scripts/oscar_ollama_env.sh
  export OLLAMA_FLASH_ATTENTION=$FA; kill $OLLAMA_PID; sleep 3
  ollama serve > logs/bench-serve-$SLURM_JOB_ID-$FA.log 2>&1 & OLLAMA_PID=$!
  for i in $(seq 1 60); do curl -s http://127.0.0.1:11434/api/version >/dev/null && break; sleep 2; done
  python - <<'PY'
import json, sys, urllib.request
sys.path.insert(0, "src")
from collect_outputs import sources
from llm import fill, load_prompt
s = [x for x in sources(["dev"]) if x["partition"] == "dev"][1]
system, user_t, _ = load_prompt("extract_v1")
for i in range(3):
    body = {"model": "qwen3:32b", "stream": False, "think": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": fill(user_t, problem_text=s["text"])}],
            "options": {"temperature": 0, "seed": 2880, "num_predict": 4096}}
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/chat",
                  data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=600))
    ns = 1e9
    print(f"run{i}: load={r.get('load_duration',0)/ns:.1f}s prompt={r['prompt_eval_count']}tok/{r['prompt_eval_duration']/ns:.2f}s "
          f"gen={r['eval_count']}tok/{r['eval_duration']/ns:.1f}s -> {r['eval_count']/(r['eval_duration']/ns):.1f} tok/s "
          f"total={r['total_duration']/ns:.1f}s", flush=True)
PY
  ollama ps
  kill $OLLAMA_PID; sleep 3
done
nvidia-smi --query-gpu=name,clocks.sm,clocks.max.sm,power.draw --format=csv
echo "bench done"
