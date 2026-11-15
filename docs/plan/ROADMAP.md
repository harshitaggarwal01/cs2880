# Roadmap

**Project:** SafeAdapt-Math — auditing and verifying LLM accessibility rewrites of math word problems
**Course:** Harvard COMPSCI 2880, AI for Social Impact, Fall 2026 · two-person team
**Plan version:** 1.0 (2026-11-02) · **Active branch:** `dev-phases` (merge to `main` at phase gates only)

## The phases in one table

| Phase | Scope | Dates | Exit gate |
|---|---|---|---|
| **1 · MVP** (current) | Run the dossier study end to end on real APIs: 124 frozen problems × 2 generators × {plain, chunked} + realistic teacher prompt on the 100 main problems + deterministic baseline; 3-layer verifier; one repair pass; blinded human labels; prespecified analysis; report | Nov 2 – Nov 29 | Labels adjudicated (κ/AC1 ≥ 0.7 on SAFE); `phase1_report.md` generated; ledger ≤ $30 |
| **2 · Methods** | Four offline methods on Phase-1 outputs: conformal risk control (guaranteed PASS), cost-aware cascade, prediction-powered inference, offline contextual-bandit policy; red-team robustness as stretch | Coded Nov 7–20 on synthetic data; run on real labels Nov 23–29 | Tests green; `analysis/<module>.csv`; method notes; one figure each in the report |
| **3 · Real-world** | External-tool audit harness (manual capture + loader), teacher-prompt survey instrument, Streamlit demo, distilled free verifier layer (stretch) | Nov 10 – Dec 1 | Demo runs offline from the main run; template + loader tested; protocol and survey docs reviewed |
| **4 · Write-up & release** | Final report, reproducibility doc, data-release packaging, failure gallery, handoffs | Nov 30 – Dec 5 | Report complete; `make release` reproduces checksums; all tests green |

Detailed phase docs: [PHASE1.md](PHASE1.md) · [PHASE2.md](PHASE2.md) · [PHASE3.md](PHASE3.md) · [PHASE4.md](PHASE4.md). Handoffs: [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md), `HANDOFF_PHASE<n>.md`.

## Schedule against the check-ins

| Dates | What exists by then | Check-in |
|---|---|---|
| Nov 2–3 | Plan docs; Phase-1 gaps fixed; calibration sheets; orchestrator passes mock end-to-end; Anthropic-only config | **Check-in 1 (Nov 3):** show the pilot, the plan, and the running pipeline |
| Nov 3–5 | Both teammates relabel the 70 pilot outputs blind → agreement → rubric v1 frozen; real `--pilot` on the dev set; config frozen; GSM-IC go/no-go | |
| Nov 5–7 | Main generation, realistic condition, baseline, verify, repair, re-verify, sheets, ledger (API-only, blind to labels) | |
| Nov 7–10 | Annotation started; Phase-2 modules coded and unit-tested on synthetic data; variance run | **Check-in 2 (~Nov 10):** real outputs, first labels, method notes |
| Nov 10–22 | Annotation: A labels everything, B labels the 30% stratified subset; agreement before adjudication | |
| Nov 23–29 | Adjudication; evaluate + report; Phase-2 methods on real labels; demo in offline mode | |
| Nov 30 – Dec 5 | Final report, release packaging, handoffs | **Final** |

## Why the order is this way

- **Human annotation is the bottleneck** (~16 h per person). Everything the sheets need — generation, verification, repair — is API-only and blind to labels, so it runs in the first four days. Phase-2 code is written against synthetic data while labels are being produced, then re-run on the real labels.
- **Layer ablations, the cascade and the conformal calibration are computed offline** from stored verifier fields. No extra API calls.
- **The realistic teacher prompt is co-primary** (RQ2). The pilot showed that is where leakage lives.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-15 | **Option 2: full matrix (Haiku, Sonnet, Qwen rewriters; every critic on every output) with lean labelling**, prespecified before any main-run generation: label 50% of source problems for the careful prompts (paired across rewriters and styles), all realistic-prompt outputs, every repair whose original is labelled, 30% of the non-AI baseline (nested); two annotators split the work with 30% shared. Rates for partly labelled conditions come from PPI++ (primary verifier as predictor); hypothesis tests use labelled items only | Keeps the open-model rewriter and the self-preference test while cutting labelling from about 1,430 to about 850 items (about 14 h per annotator). Uses our own PPI method for real |
| 2026-11-15 | Fetch everything, GSM1K included (local only, never redistributed); GSM-IC moves to future work | Owner decision; without `--gsm1k` the 12 GSM1K problems were silently skipped |
| 2026-11-15 | **No paid runs until the owner adds keys; current budget is $9.** Three checker tiers with the same rewriters, sample and labelling plan: `config.matrix-budget.yaml` (Haiku primary critic + extractor, Qwen critics; about $7.2 upper bound), `config.matrix-mid.yaml` (Sonnet primary critic; about $18), `config.matrix.yaml` (Opus; about $58). A hard cap (`budget_usd`) stops any paid step that would exceed it | The full Opus checker does not fit $9. Labels stay the ground truth in every tier; a weaker primary critic lowers verifier recall and PPI's precision gain, not validity |
| 2026-11-16 | **Free models first:** `config.ollama.yaml` runs open-weight rewriters and critics on OSCAR via Ollama at $0. Closed-model critics (Claude, GPT) are added later as extra critics on the same outputs (labels reused); closed-model rewriters need their own labelling batch | Owner priority; OSCAR has Ollama. Keeps the paid budget for a strong critic |
| 2026-11-15 | Checker v1.1.1: "left"/"other" count as synonyms of "remaining" only in their quantity senses | Audit probe: an incidental "other apples" or "turn left" masked a dropped "remaining". Dev pilot unchanged (29/11/0) |
| 2026-11-15 | Refusals and empty replies are excluded from safety rates and reported per condition | A refusal gives the teacher nothing: a usefulness cost, not a safety failure |
| 2026-10-16 | Realistic teacher prompt promoted from side ablation to co-primary condition on all 100 main problems | Pilot: 13/20 unsafe under the realistic prompt vs 0/50 under constrained prompts |
| 2026-10-16 | Sample frozen: 10 dev (GSM8K train) + 100 main (GSM8K test, stratified) + 12 ASDiv + 12 GSM1K row ids; seed 2880 | Resolves the 124/135 inconsistency in the earlier documents |
| 2026-11-02 | **Anthropic-only Phase-1 run first (`anthropic-v1`)**: generators `claude-haiku-5-5` + `claude-sonnet-5-5`, critic/extractor `claude-opus-5-5` | Only an Anthropic key is available. Same-family caveat (judge favours its own family; Panickssery et al. 2024, Kim et al. 2025) is disclosed. The cross-family run `main-v1` (gpt-6-luna + gemini-3.8-flash, Sonnet critic) is a config swap when keys arrive; together they give a 4-generator comparison |
| 2026-11-02 | GSM-IC distractor set optional, default off; decide before main generation | GSM8K has few irrelevant details, so relevance leakage would be under-observed; adds ~48 annotation items |
| 2026-11-02 | All development on `dev-phases`; commits authored by the project owner only | Keeps `main` at the check-in state; attribution policy |
| 2026-11-02 | Add an open, cheap model (Qwen, via an OpenAI-compatible host or local) as a rewriter and as a critic, and run every available critic on every rewrite (`config.matrix.yaml`, Task A2) | Shows whether a free model a school could run is safe enough; tests a cheap critic for the cascade; turns the same-family caveat into a measured self-preference effect. Critics reuse labels; each extra rewriter adds about 348 items to label (or 50% + PPI) |
| 2026-11-02 | Code all future methods now with synthetic tests (online bandit + off-policy evaluation, Stackelberg audit game, small open checker, Dawid–Skene critic ensemble, iterated red-team, weighted conformal, multilingual/science/hint-level adapters) | Owner request; they run on real data once labels exist (Task H) |
| 2026-11-02 | Cheaper models implement, orchestration reviews; statistical modules (conformal/LTT, PPI, clustered logit) get a second review before being declared done | Cost control without lowering the bar on the parts a reviewer will check |
| 2026-11-11 | **Verifier v1.1 tuned on dev only:** RELATIONS_DIFFER is logged, not a review reason, when answers MATCH; new values written only as a word one…ten → REVIEW `NUMBER_WORD_ADDED` (digits unchanged); synonym classes {altogether, in total, total, combined} and {remaining, the rest, left, other}; "each" presence only; human cue names; REVIEW `CHUNK_FORMAT` | 18/40 dev reviews came from relation-type labels while every answer matched; the only REJECT was a counting word. Tuned on the 10 dev problems only; study problems unopened. Dev pilot 17/22/1 → 29/11/0 (tuning-set numbers, not rates). `TARGET_WORDING_CHANGED` threshold unchanged |
| 2026-11-11 | **Matrix design coded (Task A2):** `openai_compat` provider; `config.matrix.yaml` (run `matrix-v1`) with rewriters Haiku 5.5, Sonnet 5.5, Qwen3.8-27B and critics Opus 5.5 (primary), Sonnet 5.5, Qwen3.8-27B, Qwen3.5-9B; one Opus extractor; `verify.py --critic/--all-critics`; `critics` orchestrator step; `critic_matrix.py` (per-critic metrics, self-preference logit, ensembles, Pareto) | Qwen3.8-27B is Apache-2.0 open weights a school could self-host; OpenRouter requests are pinned to `data_collection: deny` + `zdr: true`. Primary critic is prespecified and alone drives repair and the Phase-1 analysis; other critics are an additional, labelled analysis. Which rewriters enter the main run, and full vs 50% + PPI labelling for Qwen, are still the owner's decision |

## Status (update at each gate)

| Item | Status |
|---|---|
| Plan docs, Makefile, CHANGELOG, Anthropic config | done (Nov 2) |
| Phase 1 code: gap fixes, ledger, orchestrator, calibration, prespecified analysis, report, variance, GSM-IC fetch | done (Nov 2); mock end-to-end passes all 12 steps; 108 tests green |
| Phase 2 code: conformal, cascade, PPI, policy, red-team (synthetic tests, method notes) | done (Nov 2); second review of 2A/2C/logit done (Nov 2): PPI split fixed, Firth fallback for the logit, conformal wording |
| Phase 3 code: external-audit harness + protocol, teacher survey + loader, demo, distilled layer | done (Nov 2); collection and CUHS determination pending |
| Phase 4 code: release packaging, failure gallery, reproducibility doc, final-report skeleton | done (Nov 2) |
| Real pilot with Anthropic key | done (Nov 2): 40 generations verified, $1.19; two verifier false-alarm sources found (see HANDOFF_PHASE1) |
| Calibration sheets (70 items) | made (Nov 2); both teammates label blind |
| Check-in 1 materials | done (Nov 2): `docs/checkin_1.md`, `docs/SafeAdapt-Math_checkin1.pptx` |
| Presentation docs | done (Nov 2): updates deck (11 slides), `run_examples.md`, `PROJECT_OVERVIEW.md` |
| Next-agent hand-off | done (Nov 2): `docs/plan/AGENT_PROMPT_NEXT.md` |
| Data backup to Hugging Face | done (Nov 2): private dataset `harshitaggarwal/safeadapt-math`; re-run `make hf-backup` after each milestone |
| Verifier tuning v1.1 (RELATIONS_DIFFER, number words, synonyms, cue names, chunk format) | done (Nov 11), dev only; pilot re-decided offline: 29 PASS / 11 REVIEW / 0 REJECT (v1.0: 17/22/1); 135 tests |
| Open model + generator × critic matrix code (Task A2) | done (Nov 11): provider, matrix config, multi-critic verify, critic_matrix.py; mock end to end; 161 tests. Not run on real APIs (no keys in the environment); dev-pilot matrix run ≈ $2.3, ask first |
| Audit of Cathy's Nov 11 work + Option-2 build (Nov 15) | done: lean labelling design + adjudication script, PPI in the pipeline, refusal reporting, v1.0-vs-v1.1 sensitivity table, cost estimator, hard cap, budget/mid tiers, GSM1K fetch, checker v1.1.1; Task H future-method modules (online bandit + OPE, audit game, Dawid–Skene, small checker, weighted conformal, iterated red-team, scope adapters, student-study design) |
| Rubric v1 frozen | pending: the 70 calibration items are still unlabelled (critical path) |
| Main generation, annotation, adjudication | pending |
| Phase 2–4 on real labels | pending |

## Budget

Estimates from `src/estimate_cost.py` (`make estimate CFG=... CAP=...`; upper bounds for OpenRouter models), including the variance check and the re-checking of repairs:

| Config | Checker | Main run | Dev pilot |
|---|---|---|---|
| `config.matrix-budget.yaml` (fits the current $9) | Haiku 5.5 primary critic + extractor; Qwen 27B and 9B critics | ≈ $7.2 | ≈ $0.3 |
| `config.matrix-mid.yaml` | Sonnet 5.5 primary critic; Haiku extractor and critic; Qwen critics | ≈ $18 | ≈ $0.8 |
| `config.matrix.yaml` | Opus 5.5 primary critic + extractor; Sonnet and Qwen critics | ≈ $58 | ≈ $2.5 |
| `config.anthropic.yaml` (2 rewriters) | Opus | ≈ $32 | — |

Human annotation under the lean plan: about 850 items, about 14 h per annotator (1.5 min/item); the exact count is written to `LABEL_PLAN.json` when the sheets are built.

If over budget, scope down in this order: drop the variance check → external sets to 6 + 6 → realistic condition to 60 problems → drop the program layer.
