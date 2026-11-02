# SafeAdapt demo

A small Streamlit app that shows the pipeline on one problem at a time: original, adaptation side by side, verifier
verdict with reasons, deterministic flags, risk score and cost.

## Run it

Offline (no API key; reads a finished run folder):

    pip install streamlit            # also listed in requirements.txt
    streamlit run demo/app.py -- --offline data/outputs/anthropic-v1
    make demo RUN=data/outputs/anthropic-v1

The app indexes `generations*.jsonl`, `baseline.jsonl`, `repairs*.jsonl`, every `*.verify-*.jsonl` and `ledger.csv`
in the run folder, plus the source problems in `data/frozen/`. Without `--offline` it picks `data/outputs/anthropic-v1`
if it exists, otherwise the first folder under `data/outputs/`. Pick a source in the sidebar; the four buttons show
the stored output for that condition ("Plain language", "Chunked", "Realistic teacher prompt") or the model-free
"Deterministic split", which is computed on the spot. Below, a table lists every stored output for the source.

Live (needs a key, spends a few cents):

    ANTHROPIC_API_KEY=... streamlit run demo/app.py

Choose a generator from `config.anthropic.yaml` in the sidebar, paste a problem, and press Run. The rewrite uses the
same prompt files and provider settings as the study (`prompts/<transformation>_v1.txt`).

## What it shows

| Item | Source |
| --- | --- |
| Verdict PASS / REVIEW / REJECT and reasons | `verify.decide` (stored row offline; deterministic layer only live) |
| Flags table | `deterministic_checks.check` |
| Risk score | `conformal.risk_score` (blank if that module is absent) |
| Cost | sum of `usd` in `ledger.csv` offline; `ledger.price_call` live |
| Deterministic split | `baseline.render` |

The pure logic lives in `demo/core.py` and is tested without a Streamlit server (`tests/test_phase3_demo.py`).

## Limitations

- PASS means no problems were detected under these checks. It is not a certificate of safety.
- Live mode runs the free deterministic layer only: no critic, no program check. Its risk score never goes below 2.0
  because a missing critic counts as uncertainty.
- Same-family caveat: with `config.anthropic.yaml` the generators and the critic are all Claude models, so stored
  verdicts may be optimistic.
- The policy choice from Phase 2D is not wired in; it needs human labels to learn a policy.
- One problem at a time, no authentication, no logging. Do not paste student data; use public problems only.
