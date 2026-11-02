# Phase 1 — MVP: run the study end to end

**Status:** in progress · **Owner:** both · **Dates:** Nov 2 – Nov 29 · **Code effort:** ≈ 31 h · **Annotation:** ≈ 16 h per person

## Objective

Produce the first real, labelled benchmark: how often two LLMs change the mathematics or leak solution information when asked to make grade-school word problems more accessible, under constrained and realistic prompts; how well the hybrid verifier catches unsafe rewrites; and whether one repair pass helps. Everything the dossier (§7–§15) prespecifies, run once, reported with uncertainty.

## Entry criteria

- Frozen sample (`data/frozen/`, seed 2880) — done.
- Prompts v1 frozen (`prompts/*_v1.txt`) — done.
- An API key. **Now:** Anthropic only → `config.anthropic.yaml` (`run_id: anthropic-v1`). **Later:** `config.example.yaml` (`run_id: main-v1`) when OpenAI and Gemini keys arrive.

## Model configuration while only Anthropic is available

| Role | Model | Note |
|---|---|---|
| Generator A | `claude-haiku-5-5` | cheap/fast tier, like the tools teachers use |
| Generator B | `claude-sonnet-5-5` | mid tier |
| Critic + extractor | `claude-opus-5-5` | strongest judge available |

**Caveat, stated in every result table:** generators and critic are the same model family. LLM judges favour their own family's outputs (Panickssery, Bowman & Feng 2024) and errors correlate within a provider (Kim et al. 2025). Verifier recall is still measured against *human* labels, so the headline numbers stand; what the same-family setup can inflate is the critic layer's apparent agreement with the generators. The cross-family run repeats generation with `gpt-6-luna` and `gemini-3.8-flash` under the same critic once keys arrive.

## Work items

| # | Item | Files | Reuses | Done when |
|---|---|---|---|---|
| 1.1 | Baseline rows carry the full generation schema so they flow through verify → sheets | `src/baseline.py` (`records(sources, run_id)`) | `common.sha256_text` | `verify.py` det-only runs on baseline; sheets include baseline rows |
| 1.2 | Persistent extraction cache + extractor usage logged; offline layer ablations | `src/verify.py` (`extract()`, `decide_subset()`) | `verify.decide` | `decide_subset(row, all)` == stored decision; `--layers det` needs no API |
| 1.3 | Cost/latency ledger | `src/ledger.py` | config `prices` | `ledger.csv`; totals by stage and condition |
| 1.4 | One-command orchestrator with resume | `src/run_phase1.py`, `Makefile` | `llm.done_ids` | `--mock --until sheets` passes; rerun skips done steps |
| 1.5 | Rubric calibration on the 70 pilot outputs | `src/calibrate.py` | `make_annotation_sheets`, `evaluate.agreement` | both relabel blind; κ/AC1 on SAFE ≥ 0.7; rubric v1 frozen |
| 1.6 | Prespecified analysis | `src/evaluate.py` (`prespecified_families`, `presentation_vs_baseline`, `logit_unsafe`, `layer_ablations`, `repair_outcomes`) | `mcnemar_exact`, `holm`, `cluster_boot`, `verifier_metrics` | `analysis/*.csv` written; three families only |
| 1.7 | Report with figures | `src/report.py` | all of the above | `docs/results/<run_id>_report.md` + PNGs |
| 1.8 | Variance check (single-sample caveat) | `src/variance_check.py` | `collect_outputs.run` | 20 sources × 4 conditions regenerated; flip rates reported |
| 1.9 | Optional GSM-IC distractor set | `src/fetch_data.py --gsmic` | `common.tags` | decided before main generation |
| 1.10 | Docs | `README.md`, `requirements.txt`, this file, `HANDOFF_PHASE1.md` | | |

## Data flow

```text
data/frozen/{dev,main,ext_asdiv,ext_gsm1k}.jsonl
   │  collect_outputs (plain, chunked)            → data/outputs/<run_id>/generations.jsonl
   │  collect_outputs --ablation (naive, main)    → ablation_generations.jsonl
   │  baseline --run-id                           → baseline.jsonl
   ▼
verify (det + critic + program; baseline det-only) → *.verify-critic-det-program.jsonl, extractions.jsonl
   ▼
repair (REVIEW/REJECT only, one pass)             → repairs.jsonl  →  verify again
   ▼
make_annotation_sheets (blind, 30% double)        → data/annotations/<run_id>/{sheet_A,sheet_B,KEY_DO_NOT_OPEN}.csv
   ▼  human labels → adjudicated.csv
evaluate --analysis-dir                           → analysis/*.csv
report                                            → docs/results/<run_id>_report.md + figures
ledger                                            → ledger.csv
```

## Run order (what to type)

```bash
make test                                   # offline
make calibrate                              # sheets for the pilot relabel (both annotators)
python src/calibrate.py --agreement data/calibration/pilot/sheet_A_done.csv data/calibration/pilot/sheet_B_done.csv
export ANTHROPIC_API_KEY=...
make pilot                                  # 10 dev problems, real models (~40 calls)
make phase1                                 # generate → ... → sheets → ledger (asks nothing; resumable)
make variance                               # 80 extra calls
# ... annotate ...
make evaluate RUN=data/outputs/anthropic-v1
make report   RUN=data/outputs/anthropic-v1
```

Rules that protect the result (also in README): never resample `data/frozen/`; keep the first response, retry once on API errors only; annotate blind; freeze verifier rules on dev before opening main labels.

## Risks

| Risk | Mitigation |
|---|---|
| Same-family generators and critic | Disclosed; human labels are ground truth; cross-family rerun when keys arrive |
| Few unsafe items under constrained prompts (floor effect) | Realistic condition and external sets supply positives; verifier metrics reported per condition |
| Annotation overrun | 30% double annotation; scope-down order in ROADMAP |
| Model drift (unpinned IDs) | `returned_model` logged per call; all generation within one week |
| Gemini thinking tokens truncating output (later run) | `stop_reason` logged; truncation rate reported |

## Exit gate

- `make test` green; `python src/run_phase1.py --config config.anthropic.yaml --mock --until sheets` passes.
- Real run complete; `ledger.csv` total ≤ $30.
- κ or AC1 ≥ 0.7 on SAFE before adjudication.
- `docs/results/anthropic-v1_report.md` generated.
- `HANDOFF_PHASE1.md` filled.
