# What a person must do before the final results (as of 2026-11-20)

Everything that can run without a person has run (see `docs/results/STATUS_REPORT_2026-11-20.md`).
The fillable version of this list, with the item text, is a local workbook (`HUMAN_ACTIONS_2026-11-20.xlsx`, kept outside
the repo because it quotes problems). Priority: **P0** blocks the final results; **P1** needed for a clean final; **P2** optional.

## Checklist

| # | Pri | Task | Who | Time | Blocks |
|---|---|---|---|---|---|
| 1 | P0 | Review the **5 SAFE adjudications** in `data/calibration/pilot/TO_ADJUDICATE.csv`. A said unsafe, B said safe, and the AI adjudicator chose SAFE every time. Mark each ACCEPT or OVERRIDE. | Owner (with Cathy if possible) | 15 min | The calibration claim, the stand-in labeller's score, and sign-off on the rubric |
| 2 | P1 | Sign off the other 25 AI adjudications (presentation, codes, adaptation_needed) | Owner | 30 min | The final calibration agreement table |
| 3 | P1 | Approve rubric v1.1 (`docs/annotation_guide.md`, frozen 2026-11-19) **before main labelling starts** | Owner + Cathy | 15 min | Main labelling: a later change means relabelling |
| 4 | P0 | Blind main labelling, annotator A: `data/annotations/ollama-v1/sheet_A.xlsx`, 693 items | A | 17.3 h | Every final label-dependent result |
| 5 | P0 | Blind main labelling, annotator B: `sheet_B.xlsx`, 692 items, done independently of A | B (Cathy) | 17.3 h | Same |
| 6 | P0 | Joint adjudication of the main-study disagreements among the 323 double-labelled items. Run `python src/adjudicate.py --ann data/annotations/ollama-v1`, fill the `*_final` columns, then rerun with `--resolved TO_ADJUDICATE.csv`. | A + B together | ~4–5 h (if ~40% disagree, as in calibration) | The final `adjudicated.csv` |
| 7 | P2 | Variance flip check: SAFE yes/no for both versions of 10 regenerated pairs (`data/outputs/ollama-v1/variance/flip_check_sheet.csv`) | Either annotator | 15 min | Label-flip rate (at present only text and decision flips are measured) |
| 8 | P1 | Decision D2: should the pooled PPI estimate be stratum-weighted? | Owner | 2 min | One headline number |
| 9 | P1 | Rotate the OpenRouter key (it was pasted in chat). Put the new key in `~/.config/safeadapt/openrouter.env`, chmod 600. | Owner | 5 min | Security only |
| 10 | P2 | Decision D3: what to do with the remaining OpenRouter credit (about $18.58) | Owner | 2 min | Nothing |
| 11 | P0 | After labels: Claude reruns every method on the human labels (no code changes) and the owner reviews the final report | Claude runs, owner reviews | ~1.5 h compute plus reading | The final write-up |

**Critical path:** 1 → 3 → (4 ∥ 5) → 6 → 11, roughly 17 h per annotator, then about half a day jointly.

## The 5 SAFE adjudications to review (item 1)

| annotation_id | Transformation | A | B | AI final | Labels that differ |
|---|---|---|---|---|---|
| `ad4d9631c4d` | plain | unsafe | safe | SAFE | math_fidelity, solvability_changed, presentation, failure_codes |
| `a70d86fe508` | chunked | unsafe | safe | SAFE | math_fidelity, solvability_changed, ambiguity, failure_codes |
| `ade58418190` | chunked | unsafe | safe | SAFE | math_fidelity, solvability_changed, ambiguity, failure_codes |
| `aaee7a94013` | chunked | unsafe | safe | SAFE | math_fidelity, solvability_changed, failure_codes |
| `a0b93bad8c5` | naive (realistic) | unsafe | safe | SAFE | leakage_level, presentation, failure_codes |

An adjudicator that always sides with the lenient annotator is the same failure we are testing AI judges for. If any of
these flips to UNSAFE, the adjudicated careful-prompt rate moves off 50/50 and the stand-in labeller's κ 1.00 falls.

## Decisions (item 8 and others)

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Approve rubric v1.1 as frozen | Approve before main labelling starts |
| D2 | The pooled "all" PPI row is invalid under the lean design. Fix it with a stratum-weighted pooled estimate, which edits the protected `src/ppi.py`, or report per-stratum rows only? | Fix it: one new weighted function; the per-stratum rows stay unchanged |
| D3 | Remaining OpenRouter credit, about $18.58 | Keep it unused, unless the final report needs paid judges on the repairs |
| D4 | Same annotators as in calibration (A and B)? | Yes: that keeps the calibration κ valid |
| D5 | Deadline for both sheets | Leave about 2 days afterwards for adjudication, the rerun and the write-up |
| D6 | Keep the stand-in (Mistral) results in the final report? | Appendix only, as an "AI labeller vs human" agreement finding |

## Rules for labellers

- Never open `KEY_DO_NOT_OPEN.csv`.
- A and B don't discuss items until the joint adjudication.
- Fill every key label. Any FAIL, any solvability YES, ambiguity NEW or leakage > 0 needs the offending words in `evidence`.
