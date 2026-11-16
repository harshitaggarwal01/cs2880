#!/bin/bash
# Run the free (Ollama) tier of SafeAdapt-Math on Brown's OSCAR, one job on one GPU. Submit from the repo root:
#   sbatch scripts/oscar_ollama.sbatch                      # STAGE=all (default): pilot -> gate -> main -> futures
#   STAGE=pilot sbatch -t 2:00:00 scripts/oscar_ollama.sbatch    # 10 dev problems + gate only
#   STAGE=main sbatch scripts/oscar_ollama.sbatch           # gate on the pilot, then fetch ... lean labelling sheets
#   STAGE=futures sbatch -t 6:00:00 scripts/oscar_ollama.sbatch  # label-free future methods on the finished main run
# Every stage is resumable: resubmit the same command after a timeout (.done/ markers + per-row resume).
# Models come from the CCV-hosted store (scripts/oscar_ollama_env.sh); nothing is pulled.
#SBATCH -J safeadapt-ollama
#SBATCH -p gpu
#SBATCH --qos=pri-gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a40|a6000
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 36:00:00
#SBATCH -o logs/ollama-%x-%j.out
set -euo pipefail
STAGE=${STAGE:-all}
CFG=${CFG:-config.ollama.yaml}
[ -f .venv/bin/activate ] && . .venv/bin/activate
source scripts/oscar_ollama_env.sh
RUN=$(python -c "import yaml;print(yaml.safe_load(open('$CFG'))['run_id'])")
echo "STAGE=$STAGE CFG=$CFG RUN=$RUN node=$(hostname) start=$(date -Is)"

stage_pilot() {
  python src/run_phase1.py --config "$CFG" --from pilot --until pilot
  python src/verify.py data/outputs/$RUN/pilot_generations.jsonl --config "$CFG" --all-critics
  python src/ledger.py --run data/outputs/$RUN --config "$CFG"
}
stage_gate() {
  # Stop before spending GPU-days if the dev pilot tripped a stop rule (AGENT_PROMPT_OSCAR.md section 4)
  python scripts/pilot_gate.py --run data/outputs/$RUN --config "$CFG" | tee logs/gate-${SLURM_JOB_ID:-local}.txt \
    || { echo "GATE FAILED: main run not started"; exit 2; }
}
stage_main() {
  python src/run_phase1.py --config "$CFG" --until sheets
  python src/run_phase1.py --config "$CFG" --from ledger --until ledger
}
stage_futures() {
  # Label-free methods only; the rest (conformal, cascade, PPI, policies, audit game, distill, small checker,
  # critic matrix, failure gallery) need data/annotations/$RUN/adjudicated.csv. One failure doesn't stop the others.
  set +e
  run() { echo ">>> $*"; "$@"; echo "<<< exit=$? $(date -Is)"; }
  run python src/variance_check.py --config "$CFG"
  run python src/redteam.py --config "$CFG" --iterated --rounds 3 --n 50
  run python src/critic_ensemble.py --run data/outputs/$RUN --config "$CFG"
  run python src/conformal.py --shift-demo
  run python src/report.py --run data/outputs/$RUN
  set -e
}
case "$STAGE" in
  pilot)   stage_pilot; stage_gate ;;
  main)    stage_gate; stage_main ;;
  futures) stage_futures ;;
  all)     stage_pilot; stage_gate; echo "== main $(date -Is)"; stage_main; echo "== futures $(date -Is)"; stage_futures ;;
  *) echo "unknown STAGE=$STAGE"; exit 1 ;;
esac
echo "done: STAGE=$STAGE end=$(date -Is)"
