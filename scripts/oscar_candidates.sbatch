#!/bin/bash
# Screen cheap rewriter candidates on the 10 dev problems (real prompts). ~10-15 min.
#   sbatch scripts/oscar_candidates.sbatch
#SBATCH -J safeadapt-cand
#SBATCH -p gpu-debug
#SBATCH --qos=gpu-debug
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a40|a6000
#SBATCH -c 4
#SBATCH --mem=48G
#SBATCH -t 00:45:00
#SBATCH -o logs/candidates-%j.out
set -euo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate
source scripts/oscar_ollama_env.sh
for m in phi3:latest mistral:7b gemma3:4b qwen3:4b llama3.2:1b llama3.2:3b; do
  ollama show "$m" >/dev/null 2>&1 || { echo "missing $m"; exit 4; }
done
python scripts/oscar_candidates.py config.ollama.yaml phi3:latest mistral:7b gemma3:4b qwen3:4b llama3.2:1b llama3.2:3b
echo "candidates done"
