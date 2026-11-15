# Prompt for a Claude Code agent running on OSCAR (copy everything below the line)

---

You are running on **Brown's OSCAR cluster** for **SafeAdapt-Math** (Harvard COMPSCI 2880, AI for Social Impact). The project audits AI rewrites of math word problems: do accessibility rewrites (plain language, chunked) keep the same math, and do they leak the answer or the steps? Your job is to run the **free tier**: open-weight models served by **Ollama** on an OSCAR GPU, at $0.

Repo: `https://github.com/harshitaggarwal01/cs2880`. Work on branch **`oscar-free-tier`** (cut from `dev-phases`).

## 0. Read first (about 10 minutes)
1. `docs/PROJECT_OVERVIEW.md`: what the project is.
2. `docs/plan/HANDOFF_PHASE1.md`: current state. Read "Option-2 build" and "Next owner's first steps".
3. `config.ollama.yaml` and `scripts/oscar_ollama.sbatch`: what you will run.
4. `src/llm.py`, class `OpenAICompatibleProvider`: how Ollama is called (OpenAI-compatible endpoint, JSON-schema output with a fallback, `<think>` stripping).

## 1. Hard rules
- **Git identity:**
  - Every commit is authored *and* committed as `Harshit Aggarwal <51515489+harshitaggarwal01@users.noreply.github.com>`.
  - No `Co-Authored-By` or other trailers.
  - Use `GIT_AUTHOR_NAME=... GIT_AUTHOR_EMAIL=... GIT_COMMITTER_NAME=... GIT_COMMITTER_EMAIL=... git commit`.
  - Push with `git push -u origin oscar-free-tier`. Never push to `main`.
- **No secrets in files.** The free tier needs no keys. If a key is ever needed, it comes from an environment variable named in the config (`api_key_env`), never from a file or a commit.
- **Never run models on the login node.** Use `sbatch` or an interactive GPU session (`interact -q gpu -g 1 ...` or your allocation's equivalent).
- **Blinding:**
  - Never open or print `data/calibration/pilot/KEY_DO_NOT_OPEN.csv` or `data/annotations/*/KEY_DO_NOT_OPEN.csv`.
  - Don't read or summarise the main-study outputs (`data/outputs/ollama-v1/generations*.jsonl`, `ablation_generations*`). Report only automated counts (pass/review/reject, errors, timing).
  - The 10 **dev** (practice) problems are fair game: you may read and quote their outputs.
- **Don't change** `src/conformal.py`, `src/ppi.py`, `evaluate.logit_unsafe`, the frozen sample in `data/frozen/`, the prompts in `prompts/*_v1.txt`, or the checker rules (`src/deterministic_checks.py`, `src/verify.py` decide logic).
  - You may change `config.ollama.yaml` (model tags, settings) **before** the main run only.
  - Once the main run starts, the config is frozen into the run folder. Any change after that needs a new `run_id`.
- **Tests stay green:** `python -m unittest discover -s tests` (225 tests) before every commit.
- **Report back after each step:** what you ran, the numbers, any errors, the commit SHA.

## 2. Setup (once)
```bash
cd ~/cs2880 || git clone https://github.com/harshitaggarwal01/cs2880 ~/cs2880 && cd ~/cs2880
git fetch origin oscar-free-tier && git checkout oscar-free-tier
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python -m unittest discover -s tests          # expect OK
```

On a GPU node:
- `module load ollama` if OSCAR has a module; otherwise use the user's ollama binary.
- Start the server with `ollama serve &` and run `ollama list`.
- Note the GPU (`nvidia-smi`) and its memory.

## 3. Choose the models and edit `config.ollama.yaml`
The tags in the config are **examples**. Set them from `ollama list` (pull what's missing with `ollama pull <tag>`):
- **Two rewriters from different families**, e.g. a Qwen 7–14B and a Llama or Gemma 8–12B. Different families are needed for the self-preference test. Set each one's `family` correctly: `alibaba-qwen`, `meta-llama`, `google-gemma`.
- **Primary critic and extractor:** the largest instruct model that fits the GPU with room for context, e.g. a Qwen around 32B on an 80 GB GPU. Keep the critic and extractor the same model.
- **Second critic:** one of the smaller models.
- Keep a `$0` entry in `prices:` for every tag you use.

Then run a smoke test on the GPU node. One real call per model; check the JSON comes back:
```bash
python - <<'PY'
import yaml, sys; sys.path.insert(0, "src")
from llm import make_provider, call_with_one_retry
c = yaml.safe_load(open("config.ollama.yaml"))
for s in c["generators"] + c["critics"] + [c["extractor"]]:
    p = make_provider(s)
    r = call_with_one_retry(p, "Reply with JSON {\"ok\": true}.", "ping", {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]})
    print(s.get("name", "extractor"), s["model"], r.get("error") or (r.get("json_mode"), r.get("schema_valid"), r.get("think_chars"), r.get("latency_s")))
PY
```
- If `json_mode` falls back to `json_object` or `schema_valid` is False, note it.
- If `think_chars` > 0 on Qwen, thinking is on; it works but is slower. Raise `max_tokens` if replies get cut off.

## 4. Dev pilot (10 practice problems; run now)
```bash
sbatch scripts/oscar_ollama.sbatch        # STAGE=pilot by default; adjust #SBATCH partition/time/GPU first
```
Then check the run:
- `data/outputs/ollama-v1/pilot_generations.jsonl`: count `status` values (REWRITTEN / NO_REWRITE_NEEDED), `parse_error`, `error`, `stop_reason`, and `think_chars`.
- `pilot_generations.verify-*.jsonl`: PASS/REVIEW/REJECT counts per rewriter and per critic; `program.status` MATCH rate; critic parse failures (`critic._error`).
- Mean `latency_s` per model, from the generation and verify rows. Use it to estimate the main run's hours: about 1,430 rewrites, about 1,300 judgements per critic, about 1,430 extractions.

Report the table for slide 8 of the presentation:

| Rewriter | rewrites | pass | review | reject | same answer recomputed |
|---|---|---|---|---|---|

Also give one or two short verbatim examples from the dev problems: one clean, one flagged with its reason. Commit the pilot outputs (`data/outputs/ollama-v1/pilot_*`, `extractions.jsonl`, `ledger.csv`, `config.frozen.yaml`) and push.

**Stop and fix before the main run if any of these happen:**
- more than 5% parse errors;
- critic replies that aren't valid JSON;
- answers cut off at `max_tokens`;
- a model that refuses or returns empty text.

Fix by changing model tags or settings in the config only, then rerun the pilot with `--force`.

## 5. Main run (when the owner says go)
Generation doesn't depend on the second annotator's calibration. **Labelling the main sheets must wait until the rubric is frozen.**
```bash
STAGE=main sbatch scripts/oscar_ollama.sbatch
```
This runs fetch (including GSM1K, kept local), generate, the realistic prompt, the baseline, verify, the extra critics, repair, re-verify and the lean labelling sheets. It is resumable: if the job times out, resubmit the same command, and `.done/` markers plus per-row resume skip finished work. Size `#SBATCH -t` from the pilot latencies.

After it finishes:
- Report the per-step counts and errors. Check `data/annotations/ollama-v1/LABEL_PLAN.json`: items, labelled, per annotator, hours.
- **Do not open the sheets' contents or the key.** Commit and push the run outputs and the sheets (`sheet_A/B.csv/.xlsx`, `LABEL_PLAN.json`). Before committing, make sure no GSM1K or GSM-IC text is staged:

  ```bash
  git diff --cached --name-only
  grep -l gsm1k $(git diff --cached --name-only)
  ```

  Ask the owner how to handle GSM1K rows: by default, keep those rows local and commit everything else. See `docs/plan/AGENT_PROMPT_NEXT.md` Task C step 7.

## 6. Optional, only if the owner asks
- **Variance check** (free): `python src/variance_check.py --config config.ollama.yaml`.
- **Iterated red-team** on local models (free, quarantined): `python src/redteam.py --config config.ollama.yaml --iterated --rounds 3 --n 50`.
- **Small checker, level 2:** the LoRA judge needs `torch`, `transformers`, `peft` and a GPU, plus human labels first.
- **Backup:** `make hf-backup` needs `HF_TOKEN` with write access in the environment.

## 7. How to report back
Keep it short:
- what ran (job IDs);
- counts and timing;
- errors and what you changed;
- the slide-8 table and examples;
- the commit SHA on `oscar-free-tier`;
- what's blocked and on whom.
