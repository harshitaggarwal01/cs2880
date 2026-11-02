# Handoff: Phase 1 (2026-11-02)

## State
- Branch: `dev-phases` (off `main` at `5d02d64`)
- Commit SHA: see `git log -1` on `dev-phases`; this document was written at `c192f6a` plus the PPI commit that follows it
- run_id: `anthropic-v1` (real run not started); `anthropic-v1-mock` runs end to end offline
- Config: `config.anthropic.yaml` (SHA-256 prefix `10dd8ddccdd13230`); becomes `config.frozen.yaml` inside the run folder on first use
- Tests: 101 passed / 0 failed (`make test`), covering Phase 1–4 code
- API keys: **none in this environment**. `ANTHROPIC_API_KEY` is required for the real run.

## What was run

| step | command | output path | done? |
|---|---|---|---|
| mock end-to-end | `python src/run_phase1.py --config config.anthropic.yaml --mock --until report` | `data/outputs/anthropic-v1-mock/` (gitignored) | yes — all 12 steps; `evaluate` skips until labels exist; `report` writes the pipeline-only report |
| real pilot | `make pilot` | `data/outputs/anthropic-v1/pilot_generations.jsonl` | **no** — needs the key |
| calibration sheets | `make calibrate` | `data/calibration/pilot/{sheet_A,sheet_B,KEY_DO_NOT_OPEN}.csv` | **no** — run once, then both teammates label |
| main generation … sheets | `make phase1` | `data/outputs/anthropic-v1/…`, `data/annotations/anthropic-v1/…` | **no** — after rubric v1 is frozen |

## Artifacts (code, not data)
- `src/`: 24 modules. Phase 1: `run_phase1`, `ledger`, `calibrate`, `variance_check`, `report`, plus extended `baseline`, `verify`, `evaluate`, `fetch_data`. Phase 2: `conformal`, `cascade`, `ppi`, `policy`, `redteam`. Phase 3: `import_external`, `realistic_prompts`, `distill`, `demo/`. Phase 4: `release`, `failure_gallery`.
- `docs/methods/`: one note per Phase 2/3 method with citations.
- `docs/plan/`: roadmap, four phase docs, this handoff.
- `docs/final_report.md` (skeleton), `docs/REPRODUCIBILITY.md`, `docs/external_collection_protocol.md`, `docs/survey/teacher_prompt_survey.md`, `data/external/TEMPLATE.csv`.

## Known issues / caveats
- **Same-family models.** With only an Anthropic key, generators (`claude-haiku-5-5`, `claude-sonnet-5-5`) and critic/extractor (`claude-opus-5-5`) share a family. Disclosed in `docs/plan/PHASE1.md`; the cross-family run (`config.example.yaml`, run_id `main-v1`) is a config swap when OpenAI and Gemini keys arrive.
- **Conformal guarantee wording.** `conformal.py` reports two quantities: CRC controls the *marginal* unsafe-and-passed rate; Learn-then-Test controls the *conditional* P(unsafe | PASS) that the headline claim needs, but is conservative at 60 calibration sources (on synthetic data it passes almost nothing at α ≤ 0.10). Quote the LTT row for "of what we pass, at most α is unsafe". **Pending a second review** of 2A, 2C and the clustered logit before any number is quoted.
- **Cascade weights.** With the default `--mu 1` (one human minute weighed like one unsafe item), the calibrated cascade never chooses human review. Choose λ, μ deliberately and report the Pareto frontier, not one point.
- **GSM-IC and GSM1K text** stay local (no licence declared); `data/frozen/ext_gsmic.jsonl` and `ext_gsm1k.jsonl` are gitignored. `release.py` ships ids and labels only for both.
- **Demo policy panel** is not wired until a policy is learned from real labels (`demo/README.md`).
- **Mock provider** echoes the source problem; mock runs test plumbing only, never behaviour.
- **PPI commit.** `src/ppi.py` was swept into `c192f6a` mid-edit by a broad `git add`; the agent's final version is committed separately right after. Use the later commit.
- Interim snapshot of `pilot_annotations_PRELIMINARY.csv` labels are AI-proposed; **both teammates must relabel** via the calibration sheets before any rate is quoted.

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
- [ ] Add `ext_gsmic` to `partitions` in the config before main generation? (adds ~48 annotation items; supplies relevance-leakage positives)
- [ ] Choose λ, μ for the cascade objective, or report the frontier only
- [ ] Which external tools pass the ToS check for Phase 3A
- [ ] Submit the teacher survey for a CUHS determination this semester, or defer

## Next owner's first three actions
1. Put `ANTHROPIC_API_KEY` in the environment, run `make test`, then `make calibrate`.
2. Both teammates label the calibration sheets blind; run the agreement and disagreement commands; freeze rubric v1.
3. `make pilot`, inspect `data/outputs/anthropic-v1/pilot_generations.jsonl` and the det-layer verify output, then `make phase1`.
