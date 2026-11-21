# What a person must do before the final results (updated 2026-11-20, after the owner's review)

Everything that can run without a person has run (`docs/results/STATUS_REPORT_2026-11-20.md`).
**P0** blocks the final results; **P1** needed for a clean final; **P2** optional.

## Checklist

| # | Pri | Task | Who | Status |
|---|---|---|---|---|
| 1 | P0 | Review the 5 SAFE adjudications | Owner | **DONE.** All 5 overridden to UNSAFE. |
| 2 | P1 | Review the other 25 calibration adjudications | Owner | **DONE.** 16 ACCEPT and 14 OVERRIDE in total, in `data/calibration/pilot/owner_review_2026-11-20.csv`; applied, giving `adjudicated.csv`. |
| 3 | P1 | Approve the rubric | Owner | **DONE**, as v1.2 (2026-11-20). The text now carries the owner's rulings; v1.1 had AI-written rulings that contradicted them. |
| 4 | P0 | Blind main labelling, annotator A: `data/annotations/ollama-v1/sheet_A.xlsx`, 693 items, about 17.3 h | A | **TODO**, due 2026-12-01. The sheet was re-exported with the v1.2 instructions. |
| 5 | P0 | Blind main labelling, annotator B (Cathy): `sheet_B.xlsx`, 692 items, about 17.3 h | B | **TODO**, due 2026-12-01. Done independently; do not show B the calibration overrides before B finishes. |
| 6 | P0 | Joint adjudication of the disagreements among the 323 items both label. Run `python src/adjudicate.py --ann data/annotations/ollama-v1`, fill the `*_final` columns, then rerun with `--resolved TO_ADJUDICATE.csv`. | A + B | **TODO**, 2026-12-02 to 12-03. Expect the strict-vs-lenient gap again; adjudicate it, don't average it. |
| 7 | P2 | Variance flip check (10 pairs) | Owner | **DONE.** 2 SAFE flips (v003, v009), in `variance/flip_check_scored.json`. |
| 8 | P1 | D2: stratum-weighted pooled PPI | Owner decided FIX | **DONE.** `src/ppi_pooled.py`; `ppi.py` and the per-stratum rows are untouched. |
| 9 | P1 | Rotate the OpenRouter key | Owner | **TODO** (only the owner can do it). Revoke the pasted key; put the new one in `~/.config/safeadapt/openrouter.env` and chmod 600. |
| 10 | P2 | D3: remaining OpenRouter credit (about $18.58) | Owner | **DONE**: keep it unused. |
| 11 | P0 | Rerun every method on the human labels; review the final report | Claude runs, owner reviews | **Waiting on 6.** Check the careful-prompt rate against the five calibration overrides before quoting it. |

**Critical path:** 4 ∥ 5 (by 12-01) → 6 (12-02 to 12-03) → 11.

## Decisions recorded (2026-11-20)

| ID | Decision | Owner's choice |
|---|---|---|
| D1 | Rubric | Approve the written rubric, not the AI adjudications. The written rubric is now v1.2, which matches the owner's rulings. |
| D2 | Pooled PPI | FIX with one stratum-weighted function. Per-stratum rows stay; never quote the unweighted "all" row. |
| D3 | OpenRouter credit | KEEP UNUSED until the judge prompt stops siding with the lenient label. |
| D4 | Annotators | The same A and B as in calibration. |
| D5 | Deadline | Both sheets 2026-12-01; joint adjudication 2026-12-02 and 12-03. |
| D6 | Stand-in results | Appendix only, as an AI-versus-human finding. Do not quote κ 1.00; it is 0.79 against the owner's labels. |

## Rules for labellers

- Never open `KEY_DO_NOT_OPEN.csv`.
- A and B don't discuss items until the joint adjudication.
- Fill every key label. Any FAIL, any solvability YES, ambiguity NEW or leakage > 0 needs the offending words in `evidence`.
- Rubric v1.2 highlights:
  - "If…" is a condition. Keep it on the question.
  - A dangling "If" bullet is ambiguity NEW.
  - Relevance cues are leakage 2. Step labels are leakage 1.
  - Any leak caps presentation at 2.
