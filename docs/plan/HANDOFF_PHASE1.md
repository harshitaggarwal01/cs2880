# Handoff: Phase 1 (2026-11-02; updated 2026-11-11 for verifier v1.1; 2026-11-15 for the Option-2 build)

## State
- Branch: `dev-phases` (off `main` at `5d02d64`)
- Commit SHA: see `git log -1` on `dev-phases`; last updated Nov 15 (audit + Option-2 build)
- **Next agent:** start from [`AGENT_PROMPT_NEXT.md`](AGENT_PROMPT_NEXT.md) (tasks A–G with rules and commands)
- run_id: `anthropic-v1`: real pilot done (dev set only), main run not started; `anthropic-v1-mock` runs end to end offline
- Config: `config.anthropic.yaml` (SHA-256 prefix `10dd8ddccdd13230`); becomes `config.frozen.yaml` inside the run folder on first use
- Tests: 221 passed / 0 failed (`make test`): Phase 1–4 code, verifier v1.1.1, the matrix code, lean labelling, cost controls and the Task H modules
- Verifier: **v1.1.1** (Nov 11 + Nov 15, tuned on dev only; see `docs/methods/verifier.md`). Pilot re-decided offline: 29 PASS / 11 REVIEW / 0 REJECT (v1.0: 17 / 22 / 1)
- API keys: an Anthropic key was supplied in-session on Nov 2 (not stored in the repo). For a new session, add `ANTHROPIC_API_KEY` to the environment's secrets.

## What was run

| step | command | output path | done? |
|---|---|---|---|
| mock end-to-end | `python src/run_phase1.py --config config.anthropic.yaml --mock --until report` | `data/outputs/anthropic-v1-mock/` (gitignored) | yes — all 12 steps; `evaluate` skips until labels exist; `report` writes the pipeline-only report |
| real pilot | `make pilot` + `python src/verify.py data/outputs/anthropic-v1/pilot_generations.jsonl --config config.anthropic.yaml` + `python src/ledger.py --run data/outputs/anthropic-v1 --config config.anthropic.yaml` | `data/outputs/anthropic-v1/{pilot_generations,pilot_generations.verify-critic-det-program,extractions}.jsonl`, `ledger.csv` | **yes (Nov 2)** — 40 generations, 123 calls, $1.19 |
| calibration sheets | `make calibrate` | `data/calibration/pilot/{sheet_A,sheet_B,KEY_DO_NOT_OPEN}.csv` | **yes (Nov 2)** — both teammates now label blind; do not open the key |
| main generation … sheets | `make phase1` | `data/outputs/anthropic-v1/…`, `data/annotations/anthropic-v1/…` | **no** — after rubric v1 is frozen |

## Artifacts (code, not data)
- `src/`: 24 modules. Phase 1: `run_phase1`, `ledger`, `calibrate`, `variance_check`, `report`, plus extended `baseline`, `verify`, `evaluate`, `fetch_data`. Phase 2: `conformal`, `cascade`, `ppi`, `policy`, `redteam`. Phase 3: `import_external`, `realistic_prompts`, `distill`, `demo/`. Phase 4: `release`, `failure_gallery`.
- `docs/methods/`: one note per Phase 2/3 method with citations.
- `docs/plan/`: roadmap, four phase docs, this handoff, `AGENT_PROMPT_NEXT.md`.
- Presentation and reference docs: `docs/PROJECT_OVERVIEW.md`, `docs/run_examples.md`, `docs/checkin_1.md`, `docs/SafeAdapt-Math_updates_progress.pptx` (+ `docs/slides_updates_progress.md`), `docs/SafeAdapt-Math_checkin1.pptx`.
- `docs/final_report.md` (skeleton), `docs/REPRODUCIBILITY.md`, `docs/external_collection_protocol.md`, `docs/survey/teacher_prompt_survey.md`, `data/external/TEMPLATE.csv`.

## Known issues / caveats
- **Same-family models.** With only an Anthropic key, generators (`claude-haiku-5-5`, `claude-sonnet-5-5`) and critic/extractor (`claude-opus-5-5`) share a family. Disclosed in `docs/plan/PHASE1.md`; the cross-family run (`config.example.yaml`, run_id `main-v1`) is a config swap when OpenAI and Gemini keys arrive.
- **Conformal guarantee wording.** `conformal.py` reports two quantities: CRC controls the *marginal* unsafe-and-passed rate; Learn-then-Test controls the *conditional* P(unsafe | PASS) that the headline claim needs, but is conservative at 60 calibration sources (on synthetic data it passes almost nothing at α ≤ 0.10). Quote the LTT row for "of what we pass, at most α is unsafe"; per-condition `--by` rows are descriptive. **Second review done (Nov 2):** CRC and LTT correct as coded (wording fixed); PPI fixed to the standard labelled/unlabelled split; logit separation fallback replaced by Firth + cluster bootstrap. See CHANGELOG.
- **Cascade weights.** With the default `--mu 1` (one human minute weighed like one unsafe item), the calibrated cascade never chooses human review. Choose λ, μ deliberately and report the Pareto frontier, not one point.
- **GSM-IC and GSM1K text** stay local (no licence declared); `data/frozen/ext_gsmic.jsonl` and `ext_gsm1k.jsonl` are gitignored. `release.py` ships ids and labels only for both.
- **Demo policy panel** is not wired until a policy is learned from real labels (`demo/README.md`).
- **Mock provider** echoes the source problem; mock runs test plumbing only, never behaviour.
- **PPI commit.** `src/ppi.py` was swept into `c192f6a` mid-edit by a broad `git add`; the agent's final version is committed separately right after. Use the later commit.
- Interim snapshot of `pilot_annotations_PRELIMINARY.csv` labels are AI-proposed; **both teammates must relabel** via the calibration sheets before any rate is quoted.

## Real pilot results (Nov 2; verifier decisions only, no human labels; not rates)

- 40 generations: `claude-haiku-5-5` and `claude-sonnet-5-5` × {plain, chunked} × 10 dev problems. 3 plain outputs returned `NO_REWRITE_NEEDED`. All `returned_model` values match the requested models.
- Verifier: 17 PASS, 22 REVIEW, 1 REJECT. Critic: 39 SAFE, 1 UNSURE. Program layer: 40/40 answers MATCH.
- Cost: $1.19 total (gen $0.05, critic $0.59, extract $0.56), about $0.03 per output. Extrapolates to about $20 for the main run, in line with the budget.
- **Verifier precision issues: resolved in v1.1 (Nov 11, dev only).** See `docs/methods/verifier.md` for the full table.
  1. `program:RELATIONS_DIFFER` no longer sends MATCH items to REVIEW; `relation_types_equal` is kept as a logged feature.
  2. The "taken out in three ways" REJECT is now REVIEW (`NUMBER_WORD_ADDED`): a new value written only as a word one…ten. Digits keep the strict rule; "Stories 11 to 20" still REJECTs.
  3. Synonym classes {altogether, in total, total, combined} and {remaining, the rest, left, other}; "each" counts presence only.
  4. `readable()` prints human cue names ("add", not "addinged").
  5. New REVIEW flag `CHUNK_FORMAT` (chunked fact line without "- ", or no "Question:" line).
  - Re-decided offline (no API, $0): `data/outputs/anthropic-v1/pilot_generations.verify-critic-det-program.v1_1.jsonl`; the v1.0 file is kept. **29 PASS / 11 REVIEW / 0 REJECT.** These are tuning-set numbers: optimistic by construction, not rates.
- **One real catch (still REVIEW in v1.1):** `haiku55|chunked|gsm8k-train-2016` (Vikki as bullets). "From her weekly earnings" no longer governs the 5% line, so it can be read as 5% of what's left after tax. The critic returned UNSURE → REVIEW. Keep this as a positive example for the rubric discussion.

## Open model + generator × critic matrix (Task A2, Nov 11): coded, not yet run
- `src/llm.py`: `OpenAICompatibleProvider` (`openai_compat`). Spec fields are `base_url`, `api_key_env` (the variable's name) and `model`. It uses json_schema → json_object fallback, schema validation, strips `<think>` blocks, and logs host-reported cost (`reported_cost_usd`) and `served_by`. `make_provider` refuses an `api_key` field.
- `config.matrix.yaml` (run `matrix-v1`), with a `family` on every model:
  - Rewriters: `haiku55`, `sonnet55`, `qwen38` (`qwen/qwen3.8-27b`).
  - Critics: `opus55` (primary), `sonnet55c`, `qwen38c`, `qwen35_9b`.
  - Extractor: one Opus.
  - GPT/Gemini entries are commented out until their keys exist.
  - Model IDs, licences (Apache-2.0) and price ranges were verified Nov 11; see `docs/model_selection.md`.
- `verify.py --critic NAME` / `--all-critics`. Non-primary critics write `*.verify-critic@NAME-det-program.jsonl` and reuse the extraction cache. A `critics` orchestrator step runs after `verify`. Repair and every prespecified analysis read only the primary critic's files (`common.primary_verify_files`).
- `ledger.py`: new columns `critic_name`, `family`, `cost_source`; uses the host-reported cost when present. Old runs load unchanged.
- `src/critic_matrix.py` (`make critic-matrix`): per-critic metrics, generator × critic grid, self-preference logit, ensembles and Pareto. Report section plus `fig_critics.png`. `evaluate.fit_logit_clustered` is `logit_unsafe`'s fitting rule factored out unchanged.
- **Keys:** none are set in this environment (`ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` both unset). Add them to the environment's secrets, and turn on OpenRouter's account-level training opt-out.
- **Cost estimates** (from the Nov 2 ledger: Opus critic about $0.015 per call, extraction about $0.011 per text; Qwen at the conservative table price):
  - Dev pilot through the full matrix (`make pilot CFG=config.matrix.yaml`, then `verify.py ... --all-critics` on `pilot_generations.jsonl`): about **$2.3**. Ask the owner first.
  - Main run with the matrix: about **$40–45** (Opus critic ~$16, extraction ~$13, Sonnet critic ~$8, Qwen ≤ $4, generation ~$2). Ask the owner for a cap.

## Option-2 build (Nov 15): decided and built, nothing run
- **Owner decisions (Nov 15):**
  - Option 2: full matrix with lean labelling.
  - Fetch everything, including GSM1K. GSM-IC moves to future work.
  - Budget is currently **$9**, so **no paid runs**; keys arrive after everything is built.
- **Pick a tier before the first paid run** (`make estimate CFG=<config> CAP=9`):

  | Config | Main run | Dev pilot |
  |---|---|---|
  | `config.matrix-budget.yaml` | ≈ $7.2 | ≈ $0.3 |
  | `config.matrix-mid.yaml` | ≈ $18 | ≈ $0.8 |
  | `config.matrix.yaml` | ≈ $58 | ≈ $2.5 |

  Each config carries `budget_usd`; `run_phase1.py` refuses any paid step that would exceed it.
- **Lean labelling:** about 850 of about 1,430 items are labelled, about 14 h per annotator (offline end-to-end check on `matrix-budget-v1-mock`). Merge the two sheets with `make adjudicate`.
- **Keys needed:** `ANTHROPIC_API_KEY` (Anthropic) and `OPENROUTER_API_KEY` (Qwen). Add them through the environment's secrets, never in chat or files, and turn on OpenRouter's account-level training opt-out.

## Backup to Hugging Face
`src/push_hf.py` stages everything hard to reproduce into `data/hf_staging/` (gitignored): frozen sample, real run outputs, extraction cache, ledger, labels and keys, the earlier pilot, calibration sheets, prompts, configs, checksums and a dataset card. It then uploads to the **private** dataset repo `harshitaggarwal/safeadapt-math`.
- It drops GSM1K/GSM-IC text rows, skips mock runs and `data/raw`, aborts if anything looks like a secret, and refuses to upload to a public repo.
- Usage: `make hf-stage` (dry run) or `make hf-backup` (needs `HF_TOKEN` with write scope in the environment's secrets).
- **Status (Nov 2): uploaded.** https://huggingface.co/datasets/harshitaggarwal/safeadapt-math (private, 44 files, HF commit `44c952e`, from git `64082d2`). Re-run `make hf-backup` after each real run or labelling milestone.

## How to resume
```bash
pip install -r requirements.txt && make test
export ANTHROPIC_API_KEY=...                       # or add it to the environment's secrets
make calibrate                                     # sheets for the 70-item pilot relabel (both annotators)
python src/calibrate.py --agreement data/calibration/pilot/sheet_A.csv data/calibration/pilot/sheet_B.csv
python src/calibrate.py --disagreements data/calibration/pilot/sheet_A.csv data/calibration/pilot/sheet_B.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv
# freeze rubric v1 in docs/annotation_guide.md, then:
make pilot                                         # 10 dev problems, ~40 calls
make phase1                                        # generate -> ... -> sheets -> ledger -> report (resumable)
make variance                                      # 20 sources x 4 conditions regenerated
# annotate sheet_A (all) and sheet_B (30%), adjudicate to data/annotations/anthropic-v1/adjudicated.csv, then:
make evaluate && make report
make conformal && make cascade && make ppi && make policy   # Phase 2 on real labels
```
Resume a partial run with `python src/run_phase1.py --config config.anthropic.yaml --from <step> --until <step>`; `.done/<step>` markers skip finished steps; `--force` reruns.

## Open decisions
- [x] Rewriters and labelling: **Option 2** (Haiku, Sonnet, Qwen; lean labelling with PPI), decided Nov 15
- [x] Dev-pilot matrix run (~$2.3): **approved in session on 2026-11-11, to run once `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` are in the environment** (both unset on Nov 11). **Superseded Nov 15:** run the pilot on the chosen tier (budget tier ≈ $0.3; see "Next owner's first steps"). Original commands for the full config:
  ```bash
  python src/run_phase1.py --config config.matrix.yaml --from pilot --until pilot          # 3 rewriters x 2 styles x 10 dev
  python src/verify.py data/outputs/matrix-v1/pilot_generations.jsonl --config config.matrix.yaml --all-critics
  python src/ledger.py --run data/outputs/matrix-v1 --config config.matrix.yaml           # report actual cost
  ```
  Then check per Qwen call that `think_chars` is 0 and `served_by` is a no-retention provider. Stop and report if the ledger passes $3.
- [ ] Choose the checker tier (budget ≈ $7.2 fits the current $9; mid ≈ $18; full ≈ $58). `budget_usd` is already set in each config
- [x] GSM-IC: future work (Nov 15). GSM1K: fetched by the run (`--gsm1k`), kept local
- [ ] Choose λ, μ for the cascade objective, or report the frontier only
- [ ] Which external tools pass the ToS check for Phase 3A
- [ ] Submit the teacher survey for a CUHS determination this semester, or defer

## Next owner's first steps (from Nov 15)
1. Both teammates label the 70 calibration items blind in **`data/calibration/pilot/sheet_A.xlsx` / `sheet_B.xlsx`** (dropdowns; read `docs/LABELLING_GUIDE.md` first), then run `make import-sheets ANN=data/calibration/pilot`. Run the agreement and disagreement commands, then freeze rubric v1. **This is the critical path; it needs no keys.**
2. Add the keys. Run `make estimate CFG=config.matrix-budget.yaml CAP=9`, then the dev pilot on the chosen tier: `python src/run_phase1.py --config config.matrix-budget.yaml --from pilot --until pilot`, then `python src/verify.py data/outputs/matrix-budget-v1/pilot_generations.jsonl --config config.matrix-budget.yaml --all-critics` (about $0.3). Check `think_chars` = 0 and `served_by` on the Qwen rows.
3. With the rubric frozen: `python src/run_phase1.py --config config.matrix-budget.yaml --until sheets` (fetch, including GSM1K → generate → … → lean sheets). Label (about 14 h each), then `make adjudicate ANN=data/annotations/matrix-budget-v1`, then run the `evaluate` and `report` steps, then the Task D/H analyses. Run `make hf-backup` after each milestone.
