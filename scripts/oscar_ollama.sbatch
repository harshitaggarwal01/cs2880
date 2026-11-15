#!/bin/bash
# Run the free (Ollama) tier of SafeAdapt-Math on Brown's OSCAR. Submit from the repo root:
#   sbatch scripts/oscar_ollama.sbatch            # dev pilot (10 problems): STAGE=pilot (default)
#   STAGE=main sbatch scripts/oscar_ollama.sbatch # full run through the lean labelling sheets
# Before the first run: edit the model tags in config.ollama.yaml to match `ollama list`.
# Adjust partition/GPU lines to your OSCAR allocation.
#SBATCH -J safeadapt-ollama
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH -t 08:00:00
#SBATCH -o logs/ollama-%j.out
set -euo pipefail
mkdir -p logs
STAGE=${STAGE:-pilot}
CFG=${CFG:-config.ollama.yaml}

# 1. Ollama: use the cluster module if there is one, else an ollama binary on PATH
module load ollama 2>/dev/null || true
export OLLAMA_HOST=127.0.0.1:11434
ollama serve > logs/ollama-serve-$SLURM_JOB_ID.log 2>&1 &
for i in $(seq 1 60); do curl -s http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 2; done

# 2. Pull every model named in the config (no-op if already present)
python - "$CFG" <<'PY' | while read -r m; do ollama pull "$m"; done
import sys, yaml
c = yaml.safe_load(open(sys.argv[1]))
specs = c["generators"] + c["critics"] + [c["extractor"]]
print("\n".join(sorted({s["model"] for s in specs if s.get("provider") == "openai_compat"})))
PY

# 3. Python environment (once): python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
[ -f .venv/bin/activate ] && . .venv/bin/activate

if [ "$STAGE" = pilot ]; then
  python src/run_phase1.py --config "$CFG" --from pilot --until pilot
  RUN=$(python -c "import yaml;print(yaml.safe_load(open('$CFG'))['run_id'])")
  python src/verify.py data/outputs/$RUN/pilot_generations.jsonl --config "$CFG" --all-critics
  python src/ledger.py --run data/outputs/$RUN --config "$CFG"
else
  python src/run_phase1.py --config "$CFG" --until sheets
fi
echo "done: STAGE=$STAGE CFG=$CFG"
