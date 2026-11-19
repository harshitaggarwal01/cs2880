#!/bin/bash
# AI STAND-IN labels (not ground truth): mistral-small3.2:24b fills rubric v1.1 for one shard of the labelling items.
# Shard 0 first labels the 70 calibration items, so the stand-in can be scored against the adjudicated human labels.
#   SHARD=0 NSHARDS=4 sbatch scripts/ai_label.sbatch   (one submission per shard; not a job array)
#SBATCH -J safeadapt-label
#SBATCH -p gpu
#SBATCH --qos=pri-gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a40|a6000
#SBATCH -c 4
#SBATCH --mem=32G
#SBATCH -t 06:00:00
#SBATCH -o logs/label-%x-%j.out
set -euo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate
export OLLAMA_PORT=$((20000 + SLURM_JOB_ID % 20000))   # own port: shards may share a node
source scripts/oscar_ollama_env.sh
ollama show mistral-small3.2:24b >/dev/null || { echo "FATAL: mistral-small3.2:24b missing"; exit 4; }
SHARD=${SHARD:?} NSHARDS=${NSHARDS:?}
if [ "$SHARD" = 0 ]; then
  python scripts/ai_label.py --sheets data/calibration/pilot --out data/calibration/pilot/standin --shard 0 --nshards 1
  python scripts/ai_label.py --sheets data/calibration/pilot --out data/calibration/pilot/standin --merge
fi
python scripts/ai_label.py --sheets data/annotations/ollama-v1 --out data/annotations/ollama-v1-standin --shard "$SHARD" --nshards "$NSHARDS"
echo "label shard $SHARD done $(date -Iseconds)"
