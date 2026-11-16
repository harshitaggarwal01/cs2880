#!/bin/bash
# Free-tier smoke test: one JSON call per configured model + a Qwen thinking probe. ~5-10 min.
#   sbatch scripts/oscar_smoke.sbatch
#SBATCH -J safeadapt-smoke
#SBATCH -p gpu-debug
#SBATCH --qos=gpu-debug
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a40|a6000
#SBATCH -c 4
#SBATCH --mem=48G
#SBATCH -t 00:30:00
#SBATCH -o logs/smoke-%j.out
set -euo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate
source scripts/oscar_ollama_env.sh
python scripts/oscar_smoke.py "${CFG:-config.ollama.yaml}"
ollama ps
echo "smoke done"
