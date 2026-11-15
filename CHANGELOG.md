# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning where applicable.

## [Unreleased]

### Easier labelling (2026-11-15)
- `src/sheets_xlsx.py` (`make sheets-xlsx` / `make import-sheets`): Excel sheets with dropdowns for every label, a QUICK = ALL CLEAR shortcut, a live green "done" column, frozen problem columns, and Instructions and Codes tabs. Import validates every row (enums, conflicts, evidence for flagged rows, failure codes, abstention) and writes the CSV the other scripts read.
- Calibration and main-study sheet builders also write the xlsx files; `adjudicate.py` imports newer xlsx files first.
- `docs/LABELLING_GUIDE.md`: a 10-minute quick start, with worked examples from the Nov 2 run (none from the calibration set).
- Calibration `sheet_A.xlsx` / `sheet_B.xlsx` generated. Tests: `test_sheets_xlsx.py` (3).

### Audit + Option-2 build (2026-11-15; code only, no paid API calls)
- **Lean labelling (prespecified):** `make_annotation_sheets.py --config` reads a `labelling:` block.
  - 50% of sources for the careful prompts, paired across rewriters and styles; all realistic-prompt outputs; repairs of labelled originals; 30% of the baseline, nested.
  - Two annotators split the items with 30% shared. `LABEL_PLAN.json` gives counts and hours.
  - Full design unchanged without the block.
- **`src/adjudicate.py` + `make adjudicate`:** merges the two sheets, lists disagreements in `TO_ADJUDICATE.csv`, and writes `adjudicated.csv` (annotator ADJ, provenance column).
- **PPI in the pipeline:** the `evaluate` step also runs `ppi.py`. The report gains a "Rates for every condition" section, a "Checker version sensitivity" section (`evaluate.policy_sensitivity`, `v10_style_decision`), and refusal/empty columns in the outputs table.
- **Cost controls:**
  - `src/estimate_cost.py` + `make estimate` (per step and model, from measured pilot tokens; upper bounds for OpenRouter).
  - `budget_usd` in every config and `run_phase1.py --budget`: a paid step is refused when spent (ledger) + its estimate would exceed the cap.
  - New tiers `config.matrix-budget.yaml` (Haiku primary critic + extractor, Qwen critics; about $7.2) and `config.matrix-mid.yaml` (Sonnet primary critic; about $18). The full `config.matrix.yaml` is about $58.
- **"Fetch all":** the `fetch` step passes `--gsm1k` whenever `ext_gsm1k` is in the partitions (it was silently skipped before). GSM-IC moves to future work.
- **Checker v1.1.1:** "left"/"other" offset a dropped "remaining" only in their quantity senses. Dev pilot unchanged (29/11/0). The known number-rule blind spot is documented in `docs/methods/verifier.md`.
- **Task H, future methods** (synthetic tests now, real data later):
  - `policy_online.py`: Thompson sampling, LinUCB, epsilon-greedy replay; IPS/SNIPS/DR off-policy evaluation; a feedback logger and demo widget.
  - `audit_game.py`: Stackelberg SSE by multiple LPs, robust interval variant, uniform and proportional baselines.
  - `critic_ensemble.py`: Dawid–Skene.
  - `train_checker.py`: CPU classifier, with an optional GPU LoRA judge.
  - Weighted conformal in `conformal.py` (opt-in; `--shift-demo`).
  - `redteam.py --iterated` with a held-out attack set.
  - `fetch_data.py --mgsm/--science` (licences verified: MGSM CC BY-SA 4.0, ARC CC BY-SA 4.0), `prompts/translate_plain_v1.txt`, `prompts/hint_levels_v1.txt`, `src/prompt_vars.py`, `docs/annotation_guide_hint_levels.md`, `docs/plan/STUDENT_STUDY.md`.
- Method notes for each new module; new make targets.
- Tests: `test_run_safety.py` (15) plus 45 from the Task H modules; 221 total.

### Open model + generator × critic matrix (2026-11-11, Task A2; code only, no real API calls)
- `llm.OpenAICompatibleProvider` (`openai_compat`): any OpenAI-compatible host. json_schema → json_object fallback, schema validation, `<think>` stripping, host-reported cost and serving provider logged. The key is read from the env var named in `api_key_env`
- `config.matrix.yaml` (run `matrix-v1`): rewriters Haiku 5.5, Sonnet 5.5, Qwen3.8-27B; critics Opus 5.5 (primary), Sonnet 5.5, Qwen3.8-27B, Qwen3.5-9B; `family` tags; OpenRouter routing `data_collection: deny`, `zdr: true`
- `verify.py --critic NAME` / `--all-critics`; `critic_specs`, `verify_path`; rows store `critic_name`, `critic_family`, `critic_model`; new `critics` orchestrator step (13 steps)
- `common.primary_verify_files`: report, distill, failure gallery, release and variance read primary-critic files only
- `ledger.py`: `critic_name`, `family`, `cost_source` columns; prefers host-reported cost
- `src/critic_matrix.py` + `make critic-matrix`: per-critic metrics with clustered CIs, generator × critic grid, self-preference logit, ensembles, critic-option Pareto; report section and figure
- `evaluate.fit_logit_clustered`: `logit_unsafe`'s fit rule factored out without behaviour change
- Docs: `docs/methods/critic_matrix.md`, Qwen section in `docs/model_selection.md`, CITATIONS (Zheng 2023, Verga 2024)
- Tests: `test_llm_openai_compat.py` (9), `test_critic_matrix.py` (9), `test_matrix_pipeline.py` (8); 161 total

### Verifier v1.1 (2026-11-11, dev problems only)
- `verify.decide`: `program:RELATIONS_DIFFER` is no longer a REVIEW reason when the recomputed answers MATCH; `relation_types_equal` stays in the row
- `deterministic_checks`: new values written only as a word one…ten → REVIEW `NUMBER_WORD_ADDED` (digits unchanged); synonym classes for total/remaining phrases; "each" counted by presence; human cue names in `readable()`; new REVIEW flag `CHUNK_FORMAT` for chunked outputs
- `VERIFIER_VERSION = "1.1"` stored in every verify row; `verify.py --redecide` re-decides a stored verify file offline (layer 1 recomputed, critic and program reused)
- Dev pilot re-decided offline ($0): 17/22/1 → 29 PASS / 11 REVIEW / 0 REJECT (`pilot_generations.verify-critic-det-program.v1_1.jsonl`; v1.0 file kept)
- `docs/methods/verifier.md` (version log); `docs/run_examples.md` regenerated from the v1.1 file with updated notes
- Tests: `tests/test_verifier_v11.py` (23 tests); 135 total

### Summary (2026-11-02, branch dev-phases)
All phases coded and tested offline (108 tests after the Nov 2 statistical review); mock pipeline runs end to end; real Anthropic pilot run and verified ($1.19); check-in 1 materials.

### Added
- Phase plan docs (docs/plan/)
- Makefile
- Anthropic-only config
- Phase 1 gap fixes (baseline schema, persistent extraction cache, offline layer ablations)
- ledger, orchestrator, calibration tooling, report generator, variance check, GSM-IC fetch
- Phase 2 methods: conformal, cascade, ppi, policy, redteam
- Phase 3: external audit harness, teacher prompt survey, demo, distill stub
- Phase 4: final report skeleton, release packaging
- Real pilot `anthropic-v1` (Nov 2): 40 generations on the dev set (claude-haiku-5-5, claude-sonnet-5-5 × plain, chunked), 3-layer verify (Opus critic and extractor), ledger: 123 calls, $1.19. Verifier decisions 17 PASS / 22 REVIEW / 1 REJECT; 40/40 program answers match
- Calibration sheets for the 70-item pilot relabel (`data/calibration/pilot/`)
- Check-in 1 note (`docs/checkin_1.md`) and 6-slide deck (`docs/SafeAdapt-Math_checkin1.pptx`)
- "Updates and Progress" deck, 11 slides with speaker notes (`docs/SafeAdapt-Math_updates_progress.pptx`), and its source text for the design tool (`docs/slides_updates_progress.md`)
- `docs/run_examples.md`: verbatim real outputs and checker evidence (real pilot + earlier pilot), with all 40 decisions
- `docs/PROJECT_OVERVIEW.md`: structure, methods, code map, future method plans
- `src/push_hf.py` + `make hf-stage` / `make hf-backup`: licence-aware, secret-scanned backup of run data, labels, pilot, prompts and configs to a private HF dataset repo (`harshitaggarwal/safeadapt-math`); 4 tests
- `docs/plan/AGENT_PROMPT_NEXT.md`: detailed hand-off prompt for the next agent (remaining code and steps). Now includes Task A2 (open model Qwen + full generator × critic matrix, self-preference test, critic ensembles) and Task H (code every future method: online bandit + OPE, Stackelberg audit game, small open checker, Dawid–Skene, iterated red-team, weighted conformal, broader-scope adapters, student-study design)

### Changed
- Statistical review of Phase 2 modules and the exploratory logit (2026-11-02):
  - `ppi.py`: predictor term now uses the unlabelled items only (standard PPI split); PPI++ λ uses the unlabelled count; stratified or joint source bootstrap; reduces to classical at 100% labelled. Coverage on synthetic data ≈ 0.95 (was 0.995–1.0).
  - `evaluate.logit_unsafe`: separation fallback is now Firth bias-reduced logit with source-cluster bootstrap SE/CI/p (was L1 with no inference); quasi-separation detected via warnings, max SE and |coef|; table labelled exploratory in the report.
  - `conformal.py`: LTT docstring no longer claims risk monotonicity (not needed for fixed-sequence validity); per-condition `--by` rows marked descriptive.
  - New tests: PPI all-labelled = classical, λ uses unlabelled n, super-population coverage, joint bootstrap; Firth on separated / quasi-separated data and agreement with MLE; LTT FWER under non-monotone risk.

## [0.1.0] - 2026-10-19

### Added
- Initial pipeline
- Frozen sample
- Pilot (70 outputs)
- Docs
- 13-slide deck
