#!/bin/bash
# OpenRouter critics (Claude Haiku/Sonnet 5.5, GPT-6 Luna, GPT-6.1 Sol) on the ollama-v1 rewrites, hard cap in
# config.ollama-paid.yaml (budget_usd). CPU only: API calls, no models on this node.
#   STAGE=pilot sbatch scripts/paid_critics.sbatch     # 50 dev rewrites, ~$0.5, ~15 min
#   STAGE=main  sbatch scripts/paid_critics.sbatch     # after the GPU job's verify step; ~$17 upper bound
# Key: ~/.config/safeadapt/openrouter.env (chmod 600, outside the repo) holding `export OPENROUTER_API_KEY=...`.
#SBATCH -J safeadapt-paid
#SBATCH -p batch
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH -t 12:00:00
#SBATCH -o logs/paid-%x-%j.out
set -euo pipefail
[ -f .venv/bin/activate ] && . .venv/bin/activate
KEYFILE="$HOME/.config/safeadapt/openrouter.env"
[ "$(stat -c %a "$KEYFILE" 2>/dev/null)" = "600" ] || { echo "FATAL: $KEYFILE missing or not chmod 600"; exit 2; }
set +x; . "$KEYFILE"
STAGE=${STAGE:-pilot}
echo "== paid critics, stage $STAGE, $(date -Iseconds)"
python scripts/paid_critics.py --stage "$STAGE"
[ "$STAGE" = pilot ] && python scripts/pilot_gate.py --run data/outputs/ollama-v1 --config config.ollama-paid.yaml | sed -n '/== critic/,/== extractions/p'
echo "== done $(date -Iseconds)"
