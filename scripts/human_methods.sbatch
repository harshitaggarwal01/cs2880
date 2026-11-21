#!/bin/bash
# Every label-dependent method on the HUMAN adjudicated labels (data/annotations/ollama-v1/adjudicated.csv),
# written into the real run folder. Run only after joint adjudication (python src/adjudicate.py --resolved ...).
#SBATCH -J safeadapt-human
#SBATCH -p batch
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 04:00:00
#SBATCH -o logs/human-%x-%j.out
set -uo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate
RUN=data/outputs/ollama-v1
ANN=data/annotations/ollama-v1; L=$ANN/adjudicated.csv; K=$ANN/KEY_DO_NOT_OPEN.csv
[ -f "$L" ] || { echo "FATAL: $L missing: run the joint adjudication first"; exit 2; }
if grep -q "ai_standin" "$L"; then echo "FATAL: $L contains AI stand-in labels"; exit 2; fi
mkdir -p $RUN/analysis
run() { echo ">>> $*"; "$@"; echo "<<< exit=$? $(date -Iseconds)"; }
V="$RUN/generations.verify-critic-det-program.jsonl $RUN/ablation_generations.verify-critic-det-program.jsonl"
run python src/evaluate.py --labels $L --key $K --verify $V --analysis-dir $RUN/analysis
run python src/ppi.py --run $RUN --labels $L --key $K --out $RUN/analysis/ppi.csv
run python src/ppi_pooled.py --run $RUN --labels $L --key $K --out $RUN/analysis/ppi_pooled.csv
run python src/ppi.py --run $RUN --labels $L --key $K --predictor critic --out $RUN/analysis/ppi_critic.csv
run python src/conformal.py --run $RUN --labels $L --key $K --alphas 0.02 0.05 0.1 --out $RUN/analysis/conformal.csv
run python src/conformal.py --run $RUN --labels $L --key $K --method ltt --by transformation --out $RUN/analysis/conformal_ltt.csv
run python src/cascade.py --run $RUN --labels $L --key $K --ledger $RUN/ledger.csv --config config.ollama-paid.yaml --out $RUN/analysis/cascade.csv
run python src/critic_matrix.py --run $RUN --config config.ollama-paid.yaml --labels $L --key $K --out-dir $RUN/analysis/critic_matrix
run python src/audit_game.py --run $RUN --rates $RUN/analysis/ppi.csv --out $RUN/analysis/audit_game.csv
run python src/policy.py --run $RUN --labels $L --key $K --ledger $RUN/ledger.csv --out $RUN/analysis/policy.csv
run python src/policy_online.py --run $RUN --labels $L --key $K --out $RUN/analysis/policy_online.csv
run python src/distill.py --run $RUN --labels $L --key $K --use-critic --out $RUN/analysis/distill.csv
run python src/train_checker.py --run $RUN --labels $L --key $K --out $RUN/analysis/train_checker.csv
run python src/failure_gallery.py --run $RUN --labels $L --key $K --out $RUN/analysis/failure_gallery_LOCAL_ONLY.md
run python src/report.py --run $RUN --labels $L --key $K --out docs/results/ollama-v1_human_report.md --fig-dir docs/results/figures/ollama-v1-human
echo "human-label methods done $(date -Iseconds)"
