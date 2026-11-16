# Sourced by the OSCAR Slurm scripts: start a private Ollama server on the CCV-hosted model store.
# See https://docs.ccv.brown.edu/oscar/large-language-models/ollama
module load ollama 2>/dev/null || true
export OLLAMA_MODELS=${OLLAMA_MODELS:-/oscar/data/shared/ollama_models}   # read-only; never `ollama pull` here
export OLLAMA_HOST=127.0.0.1:11434          # config.ollama.yaml points at localhost:11434
export OLLAMA_CONTEXT_LENGTH=16384          # server-side num_ctx (the OpenAI endpoint cannot set it per request)
export OLLAMA_KEEP_ALIVE=-1                 # keep models resident between calls
export OLLAMA_MAX_LOADED_MODELS=4           # 48 GB GPU holds the rewriters or critic+extractor together
export OLLAMA_NUM_PARALLEL=1                # the pipeline is sequential; save KV-cache memory
export OLLAMA_FLASH_ATTENTION=1
mkdir -p logs
SERVE_LOG=logs/ollama-serve-${SLURM_JOB_ID:-local}.log
# On a shared node another user's server may already hold the port; we must never talk to it. Fail closed:
# (1) refuse to start if anything answers on the port, (2) after startup, require that the listening socket
# belongs to OUR process. (A per-job port would also work, but config.ollama.yaml's base_url is frozen at 11434.)
if curl -s --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "FATAL: something already answers on 127.0.0.1:11434 (another user's server?); resubmit"; exit 3
fi
ollama serve > "$SERVE_LOG" 2>&1 &
OLLAMA_PID=$!
trap 'kill $OLLAMA_PID 2>/dev/null || true' EXIT
for i in $(seq 1 90); do curl -s http://127.0.0.1:11434/api/version >/dev/null && break; sleep 2; done
if ! kill -0 $OLLAMA_PID 2>/dev/null; then
  echo "FATAL: our ollama serve exited (port 11434 taken by another server?)"; tail -5 "$SERVE_LOG"; exit 3
fi
if ! ss -ltnpH 'sport = :11434' 2>/dev/null | grep -q "pid=$OLLAMA_PID,"; then
  echo "FATAL: the listener on 127.0.0.1:11434 is not our ollama (pid $OLLAMA_PID)"; ss -ltnH 'sport = :11434'; exit 3
fi
echo "ollama $(ollama --version 2>&1 | tail -1) | models: $OLLAMA_MODELS"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

# Check (never pull) every model the config names
CFG=${CFG:-config.ollama.yaml}
for m in $(python - "$CFG" <<'PY'
import sys, yaml
c = yaml.safe_load(open(sys.argv[1]))
specs = c["generators"] + c["critics"] + [c["extractor"]]
print(" ".join(sorted({s["model"] for s in specs if s.get("provider") == "openai_compat"})))
PY
); do
  ollama show "$m" >/dev/null 2>&1 || { echo "FATAL: model $m not in $OLLAMA_MODELS"; exit 4; }
done
echo "all config models present"
