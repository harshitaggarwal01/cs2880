# Handoff: Phase 1 (2026-11-02)

## State
- Branch: `dev-phases` (off `main` at `5d02d64`)
- Commit SHA: see `git log -1` on `dev-phases`; last updated after `33e930a` (run examples doc)
- **Next agent:** start from [`AGENT_PROMPT_NEXT.md`](AGENT_PROMPT_NEXT.md) (tasks A–G with rules and commands)
- run_id: `anthropic-v1`: real pilot done (dev set only), main run not started; `anthropic-v1-mock` runs end to end offline
- Config: `config.anthropic.yaml` (SHA-256 prefix `10dd8ddccdd13230`); becomes `config.frozen.yaml` inside the run folder on first use
- Tests: 112 passed / 0 failed (`make test`), covering Phase 1–4 code
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
- **Verifier precision issues to resolve before the main run:**
  1. `program:RELATIONS_DIFFER` fires on 18/40 even though every recomputed answer matches. Relation-type comparison is too strict; it alone drives most REVIEWs. Options: drop it from `decide` when the values MATCH, or keep it as a logged feature only.
  2. The one REJECT (`sonnet55|plain|gsm8k-train-2016`, the Vikki pay problem) is a false alarm. The rewrite says "taken out in three ways", and "three" equals a value derivable from the source. Counting words ("three ways", "two steps") should not count as leaked derived values.
  Both are verifier-tuning decisions. Make them on the dev set only, before main generation, and record them in the decision log.
- **One real catch:** `haiku55|chunked|gsm8k-train-2016` (Vikki as bullets). "From her weekly earnings" no longer governs the 5% line, so it can be read as 5% of what's left after tax. The critic returned UNSURE → REVIEW. Keep this as a positive example for the rubric discussion.
- Cosmetic: the det flag detail prints regex-derived cue names (e.g. "addinged" for `add(?:ing|ed)?`). It affects display only, not decisions; fix `readable()` in `src/deterministic_checks.py` when tuning.

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
- [ ] Which rewriters go into the main run (Haiku, Sonnet, Qwen, and GPT/Gemini if keys arrive)? Full or 50% + PPI labelling for the open rewriter? (Task A2)
- [ ] Add `ext_gsmic` to `partitions` in the config before main generation? (adds ~48 annotation items; supplies relevance-leakage positives)
- [ ] Choose λ, μ for the cascade objective, or report the frontier only
- [ ] Which external tools pass the ToS check for Phase 3A
- [ ] Submit the teacher survey for a CUHS determination this semester, or defer

## Next owner's first three actions
1. Decide the two verifier-precision fixes above (dev set only); re-verify the pilot.
2. Both teammates label the calibration sheets blind; run the agreement and disagreement commands; freeze rubric v1.
3. With rubric v1 frozen and the key in the environment: `make phase1` (≈ $20; ask first).
