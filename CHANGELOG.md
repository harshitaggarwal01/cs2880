# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning where applicable.

## [Unreleased]

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
