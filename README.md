# SafeAdapt-Math

**Preserving the math while simplifying the words: auditing and verifying LLM accessibility adaptations of math word problems.**
Harvard COMPSCI 2880 (AI for Social Impact), Fall 2026.

## Start here

| If you want… | Read |
|---|---|
| Latest check-in (Nov 3): progress and first real results | [`docs/checkin_1.md`](docs/checkin_1.md) · slides [`docs/SafeAdapt-Math_checkin1.pptx`](docs/SafeAdapt-Math_checkin1.pptx) |
| Structure, methods, code map and future plans | [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) |
| Picking up the work (agent or teammate): remaining tasks, rules, commands | [`docs/plan/AGENT_PROMPT_NEXT.md`](docs/plan/AGENT_PROMPT_NEXT.md) |
| The plan in one page | [`docs/one_page_brief.md`](docs/one_page_brief.md) |
| Real outputs and checker verdicts from our runs (Nov 2 API pilot + earlier pilot) | [`docs/run_examples.md`](docs/run_examples.md) |
| Real LLM outputs to show the professor | [`docs/professor_examples.md`](docs/professor_examples.md) |
| The full project plan | [`docs/dossier.md`](docs/dossier.md) |
| What to read, in order | [`docs/reading_list.md`](docs/reading_list.md) |
| How to label outputs | [`docs/annotation_guide.md`](docs/annotation_guide.md) |
| What was wrong in the earlier documents | [`docs/source_audit.md`](docs/source_audit.md) |
| Which models and settings, and why | [`docs/model_selection.md`](docs/model_selection.md) |
| The earlier ChatGPT documents (superseded) | [`docs/archive/`](docs/archive/) |

## Status (2026-11-02)
- **Done:**
  - design frozen;
  - 134 source problems sampled and frozen (`data/frozen/`);
  - prompts v1 frozen;
  - real pilot run on the 10 dev problems (`pilot/`, 70 outputs, preliminary labels);
  - code for generation, verification, repair, annotation sheets and analysis;
  - passing offline tests, including a mock end-to-end run.
- **Done on `dev-phases` (Nov 2):**
  - all four phases coded: one-command pipeline (`src/run_phase1.py`, `Makefile`), ledger, report, variance check,
    calibration tooling, GSM-IC option, Anthropic-only config; Phase 2 methods, Phase 3 audit harness/survey/demo,
    Phase 4 release packaging;
  - 108 offline tests pass; statistical review of conformal, PPI and the logit done (fixes in `CHANGELOG.md`);
  - **real Anthropic pilot** (`data/outputs/anthropic-v1/`): 40 rewrites (Haiku, Sonnet × plain, chunked) on the
    10 dev problems, fully verified: 17 PASS / 22 REVIEW / 1 REJECT, 40/40 answers recompute equal, $1.19 total.
    Two checker false-alarm sources were found (see `docs/plan/HANDOFF_PHASE1.md`);
  - calibration sheets for the 70-item relabel (`data/calibration/pilot/`).
- **Nov 11–15:**
  - Checker v1.1/v1.1.1 (dev only).
  - Open-model (Qwen) generator × critic matrix.
  - Option-2 lean labelling with PPI.
  - Cost estimator, hard cap and budget/mid/full tiers.
  - Every future method coded (online bandit + off-policy evaluation, Stackelberg audit game, Dawid–Skene critic ensemble, small open checker, weighted conformal, iterated red-team, multilingual/science/hint-level adapters).
  - 221 tests.
- **In progress:** both teammates label the 70 calibration items blind (critical path). Paid runs wait for keys; the budget tier fits $9.
- **Next:**
  1. Tune the two checker false-alarm rules on the dev problems; re-verify the pilot (about $1).
  2. Both teammates label `data/calibration/pilot/sheet_{A,B}.csv` blind, check agreement, freeze rubric v1.
  3. Main generation `make phase1` (about $20), then annotation.

## Branches and runs
`main` holds the check-in state (what was reviewed and shown); `dev-phases` is active development and may be
mid-change. Two run ids are defined: `main-v1` is the cross-family design in `config.example.yaml` (GPT-6 Luna and
Gemini 3.8 Flash under audit, Claude as critic; needs `OPENAI_API_KEY` and `GEMINI_API_KEY`), and `anthropic-v1`
(`config.anthropic.yaml`) is an Anthropic-only run that can start now with just `ANTHROPIC_API_KEY`. The caveat on
`anthropic-v1`: generators, critic and extractor come from the same model family, so correlated errors are not
controlled and verifier results from it are a dry run, not the audit.

## Roadmap
Phase-by-phase plan and open decisions: [`docs/plan/ROADMAP.md`](docs/plan/ROADMAP.md).

## Quick start
```bash
python -m pip install -r requirements.txt
python src/fetch_data.py                      # GSM8K + ASDiv into data/raw/ (checksums verified)
python -m unittest discover -s tests -v       # all offline; includes a mock end-to-end run

cp config.example.yaml config.yaml            # freeze before the main run
export OPENAI_API_KEY=... GEMINI_API_KEY=... ANTHROPIC_API_KEY=...
python src/collect_outputs.py --config config.yaml --pilot      # dev problems, real generators
python src/collect_outputs.py --config config.yaml              # main + external, plain & chunked
python src/collect_outputs.py --config config.yaml --ablation   # realistic teacher prompt, 100 main problems
python src/baseline.py data/frozen/main.jsonl > data/outputs/main-v1/baseline_main.jsonl
python src/verify.py data/outputs/main-v1/generations.jsonl --config config.yaml
python src/repair.py data/outputs/main-v1/generations.jsonl data/outputs/main-v1/generations.verify-critic-det-program.jsonl --config config.yaml
python src/make_annotation_sheets.py data/outputs/main-v1/generations.jsonl data/outputs/main-v1/ablation_generations.jsonl data/outputs/main-v1/repairs.jsonl
python src/evaluate.py --labels <adjudicated.csv> --key data/annotations/main-v1/KEY_DO_NOT_OPEN.csv --verify <verify.jsonl>
```
**Offline dry run.** Add `--mock` to `collect_outputs.py`, `verify.py` or `repair.py`. Mock runs write to `*-mock` folders only.

**GSM1K text.** Run `python src/fetch_data.py --gsm1k` (needs `datasets`). The GSM1K card declares no license, so keep the text local.

**GSM-IC (optional).** `python src/fetch_data.py --gsmic` downloads the two GSM-IC splits (Shi et al., ICML 2023), prints the
repository's licence status (no LICENSE file; citation requested), and freezes 12 distractor problems to
`data/frozen/ext_gsmic.jsonl`, spread over the role × number × topic labels. Add `ext_gsmic` to `partitions:` in your config
*before* the main generation if you want it; the text is local only, like GSM1K.

## One-command pipeline
```bash
make help                                                    # every target, with what it writes
make phase1 MOCK=--mock                                      # offline: fetch -> generate -> verify -> repair -> sheets
python src/run_phase1.py --config config.anthropic.yaml --until sheets   # real Anthropic-only run, stop at the sheets
```
Each step is skipped when its output already exists, so a run can be resumed after an interruption.

## Calibration
Both teammates label all 70 pilot outputs blind, then compare, adjudicate and freeze rubric v1.
```bash
python src/calibrate.py --make-sheets                        # data/calibration/pilot/{sheet_A,sheet_B,KEY_DO_NOT_OPEN}.csv
python src/calibrate.py --agreement A.csv B.csv              # kappa / Gwet AC1 per label (markdown)
python src/calibrate.py --disagreements A.csv B.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv   # -> disagreements.csv
python src/calibrate.py --compare-preliminary adjudicated.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv
```
`--compare-preliminary` scores the AI preliminary labels in `pilot/` against the human adjudicated ones; it is a rubric
sanity check, not a result. Open the key only after both sheets are complete.

## Rules that protect the result
1. Never resample `data/frozen/`. Never touch `main` while developing prompts or the rubric: use `dev`.
2. Keep the first response; retry once on API errors only. Never regenerate because an output looks bad.
3. Annotate blind: do not open `KEY_DO_NOT_OPEN.csv` or verifier outputs until labels are adjudicated.
4. Freeze verifier rules on dev before looking at main labels.
5. The pilot and the constructed stress cases are illustrations. Never quote them as rates.
