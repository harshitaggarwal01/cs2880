# Phase 4 — Write-up, reproducibility, release

**Status:** skeletons and release code done (Nov 2); write-up pending · **Owner:** both · **Dates:** Nov 30 – Dec 5 · **Effort:** ≈ 20 h

## Objective

Turn the run into a report someone else can check, and a release someone else can use, without over-claiming.

## Work items

| # | Item | Files | Done when |
|---|---|---|---|
| 4.1 | Final report | `docs/final_report.md` (mirrors dossier §1–§17; result placeholders bound to `analysis/*.csv`); `src/report.py --final` | Every number in the report traces to a CSV in `analysis/` |
| 4.2 | Reproducibility | `docs/REPRODUCIBILITY.md`: commit, `config.frozen.yaml` SHA-256, seeds, `make phase1` from scratch, `CHECKSUMS.sha256` regeneration | A clean clone reproduces the frozen sample and the analysis from the stored outputs |
| 4.3 | Data release | `src/release.py` (`package(run_dir, out_dir)`) → `data/release/` | Release contains only what the licences allow (table below); `test_release_excludes_gsm1k_text` green |
| 4.4 | Failure gallery | `docs/results/failure_gallery.md` built from adjudicated FAIL / leakage items, verbatim, with labels and verifier verdicts | Every example has provenance (output_id, model, prompt version) |
| 4.5 | Handoffs | `docs/plan/HANDOFF_PHASE4.md`; `CHANGELOG.md` final entry; `ROADMAP.md` status | A new team member can resume from the docs alone |

## What may be released

| Source | Text | Adaptations | Labels | Terms |
|---|---|---|---|---|
| GSM8K-derived (dev, main) | yes | yes | yes | MIT |
| ASDiv | yes, with attribution file | yes | yes | CC BY-NC 4.0 (non-commercial) |
| GSM1K | **no** (ids only) | **no** (they paraphrase the text) | yes | No licence declared on the dataset card |
| GSM-IC (if used) | per repository licence | per licence | yes | check `LICENSE` in the GSM-IC repo |
| External tool captures | **no** | **no** | yes, aggregate | Tool terms of service |

## Report structure (final_report.md)

1. Problem and why it matters · 2. Prior work and novelty · 3. Theory: accommodation vs modification · 4. Research questions · 5. Data · 6. Conditions and models (with the same-family caveat) · 7. Annotation and agreement · 8. Results: fidelity and leakage rates; realistic vs constrained; verifier recall and ablations; repair; presentation vs baseline · 9. Methods: guarantee curve, cascade frontier, PPI, policy · 10. Cost · 11. Limitations and threats to validity · 12. Decision rules and recommendations · 13. Social-impact statement · 14. Future work · References · Appendices: prompts, rubric, failure gallery.

## Claims policy (carry into the report)

- No claim of learning gains or diagnosis-specific benefit.
- PASS means "no problems detected under these checks at guarantee level α", never "proven equivalent".
- Pilot numbers and constructed stress cases are never quoted as rates.
- "Use deterministic formatting" or "humans must review everything" are reported as findings if the data say so.

## Exit gate

Report complete and internally consistent with `analysis/`; `make release` reproduces `CHECKSUMS.sha256`; all tests green; handoff written.
