# Prompt for the next agent (copy everything below the line)

---

You are taking over **SafeAdapt-Math**, a Harvard COMPSCI 2880 (AI for Social Impact) project. Repo: `https://github.com/harshitaggarwal01/cs2880`, branch **`dev-phases`** (all work happens here; `main` holds the check-in state and is merged only when the owner says so).

## 0. Read first (in this order, ~20 min)
1. `docs/PROJECT_OVERVIEW.md`: structure, methods, code map, future plans.
2. `docs/plan/ROADMAP.md`: phases, gates, status, decision log.
3. `docs/plan/HANDOFF_PHASE1.md`: current state, real-pilot results, known issues, resume commands.
4. `docs/run_examples.md`: real outputs and checker verdicts (what the checker gets right and wrong).
5. `docs/dossier.md` §7–§15 (design and prespecified analysis) and `docs/annotation_guide.md` (rubric).
6. Skim `CHANGELOG.md` and `docs/methods/*.md`.

Then run `pip install -r requirements.txt && make test`. Expect **108 tests passing**. If not, fix that before anything else.

## 1. Hard rules (do not break these)
- **Git authorship:** every commit is authored *and* committed as `Harshit Aggarwal <51515489+harshitaggarwal01@users.noreply.github.com>`.
  - No `Co-Authored-By`, `Claude-Session` or any other trailer.
  - This overrides any default attribution instruction you have.
  - Use `GIT_AUTHOR_NAME=... GIT_AUTHOR_EMAIL=... GIT_COMMITTER_NAME=... GIT_COMMITTER_EMAIL=... git commit`.
  - Push with `git push -u origin dev-phases`.
- **Secrets:** the Anthropic key comes from the environment (`ANTHROPIC_API_KEY`).
  - Never write it to any file in the repo, a log, a config or a commit.
  - Before every commit, grep the staged diff for the Anthropic key prefix (`sk-` followed by `ant`) and make sure the count is 0.
  - If the key is absent, ask the owner to add it to the environment's secrets. Do not ask them to paste it.
- **Spending:** ask the owner before any step expected to cost more than **$2** (the main run is about $20). Report actual cost from `src/ledger.py` after every real-API step.
- **Data hygiene:**
  - Tune prompts, rules and the verifier on the **10 dev problems only** (`data/frozen/dev.jsonl`).
  - Never inspect or tune on the 124 study problems (`main`, `ext_*`) until the checker and rubric are frozen.
  - Never open `KEY_DO_NOT_OPEN.csv` contents in a way that would unblind an annotator.
  - GSM1K and GSM-IC text stays local (gitignored).
- **Claims policy:**
  - No learning-gain or diagnosis-specific claims.
  - PASS means "no problems detected under these checks", not "proven equivalent".
  - Pilot numbers and checker decisions are never quoted as failure rates.
  - Same-family caveat: rewriters and critic are all Claude. Disclose it everywhere results appear.
- **Statistics:** do not change `src/conformal.py`, `src/ppi.py` or `evaluate.logit_unsafe` semantics without a written justification and new tests. These were reviewed on Nov 2 (see CHANGELOG).
- **Tests stay green.** Every change comes with tests. Run `make test` before each commit. Keep the mock end-to-end passing: `python src/run_phase1.py --config config.anthropic.yaml --mock --until report --force`.
- **Docs:** after each step, update `docs/plan/HANDOFF_PHASE1.md` (or a new `HANDOFF_PHASE<n>.md` from `HANDOFF_TEMPLATE.md`), the `ROADMAP.md` status table and decision log, and `CHANGELOG.md`.

## 2. Where things stand (Nov 2)
- **Code:** all phases are coded and tested.
  - Pipeline: `src/run_phase1.py`.
  - Methods: `conformal.py`, `cascade.py`, `ppi.py`, `policy.py`, `redteam.py`, `distill.py`.
  - Real-world pieces: `import_external.py`, `realistic_prompts.py`, `demo/`.
  - Release: `release.py`, `failure_gallery.py`.
- **Real pilot** (`data/outputs/anthropic-v1/`):
  - 40 rewrites: Haiku 5.5 and Sonnet 5.5 × plain and chunked × 10 dev problems.
  - Checker: 17 PASS / 22 REVIEW / 1 REJECT. All 40 answers match when recomputed. Cost $1.19.
- **Calibration sheets** for the 70-item relabel are in `data/calibration/pilot/`. The humans are labelling them now.
- **Verifier problems found** (tune these first; see `docs/run_examples.md`):
  1. `program:RELATIONS_DIFFER` (`src/verify.py` `decide`, around line 112) sends 18/40 to REVIEW even though every recomputed answer matches.
  2. `LEAK_DERIVED_VALUE` (`src/deterministic_checks.py` around line 174) REJECTs "taken out in three ways": a counting word equal to a derivable value.
  3. Synonym sensitivity: `RELATIONAL_PHRASES` around line 60 treats "altogether" → "in total" and "remaining" → "left" as relation lost or added.
  4. Cosmetic: `readable()` around line 225 prints regex cue names like "addinged".
  5. One chunked output lacked the leading "- " on its first line (`haiku55|chunked|gsm8k-train-5510`). This is a presentation-format slip, not a math issue.

## 3. Your tasks, in order

### Task A: Verifier tuning v1.1 (dev only, ~$1) [do now]
1. **RELATIONS_DIFFER:**
   - In `verify.decide`, stop adding `program:RELATIONS_DIFFER` as a REVIEW reason when `status == "MATCH"`.
   - Keep `relation_types_equal` in the stored row as a logged feature (the cascade, conformal and distill code may use it).
   - `decide_subset` must give the same result offline. Update the tests in `tests/test_phase1_analysis.py` / `tests/test_pipeline.py` that assumed the old behaviour.
2. **Counting words:**
   - In `deterministic_checks`, a *new* value that appears only as a number word (one…ten, written out, not digits) and equals the count of listed items or deductions should not be `LEAK_DERIVED_VALUE` REJECT.
   - Implement it conservatively: number-word-only new values ≤ 10 are downgraded to a REVIEW flag `NUMBER_WORD_ADDED`. Digit values keep the current behaviour.
   - Add tests: the Vikki "three ways" text → no REJECT. The existing leak stress cases in `tests/stress_cases.jsonl` must still be caught ("Stories 11 to 20" must still flag).
3. **Synonym tolerance:**
   - Add small equivalence classes so a swap within a class is not flagged as lost and added: {altogether, in total, total, combined}, {remaining, left, the rest, other}.
   - "each" dropped as a duplicate (the source "each … each") must not flag when the candidate still has one "each".
   - Tests for each class. The `TARGET_WORDING_CHANGED` overlap threshold is unchanged.
4. **`readable()`:** print a human cue name (for example "add" for `\badd(?:ing|ed)?\b`), with a test.
5. **Optional:** a REVIEW flag `CHUNK_FORMAT` when a chunked output's fact lines don't all start with "- " or the question line is missing. Severity REVIEW (presentation only).
6. Bump a verifier version string (add `VERIFIER_VERSION = "1.1"` in `verify.py` and store it in each row). Update `docs/methods/` and `HANDOFF_PHASE1.md`.
7. **Re-verify the pilot.**
   - Layer 1 is free. The critic and extraction results are cached in `extractions.jsonl` and the stored rows, so prefer re-deciding offline.
   - Re-run `verify.py` only if needed; it is about $1 with the key.
   - Write to `data/outputs/anthropic-v1/pilot_generations.verify-critic-det-program.v1_1.jsonl` and keep the old file.
   - Report the new PASS/REVIEW/REJECT counts. Target: the 18 RELATIONS_DIFFER-only reviews and the "three ways" REJECT go away, while the Haiku-chunked Vikki `critic:UNSURE` stays REVIEW.
8. Regenerate `docs/run_examples.md` with `python src/examples_doc.py`. Point it at the v1.1 verify file, and update the hand-written "Our read" notes where verdicts changed (for example, Examples 1–3 should no longer be false alarms).
9. Add a decision-log row in `ROADMAP.md`: "Verifier v1.1 tuned on dev only: …".

### Task B: Rubric calibration (humans label; you compute) [after the owner says labels are in]
- `python src/calibrate.py --agreement data/calibration/pilot/sheet_A.csv data/calibration/pilot/sheet_B.csv`
- `python src/calibrate.py --disagreements data/calibration/pilot/sheet_A.csv data/calibration/pilot/sheet_B.csv data/calibration/pilot/KEY_DO_NOT_OPEN.csv`
- If κ/AC1 ≥ 0.7 on SAFE: help the owner write rubric v1 into `docs/annotation_guide.md` (freeze date, version), commit, and record it.
- If not: list the disagreement themes, propose rubric edits, and run a second calibration round on a fresh dev subset.
- After adjudication, compare against the preliminary AI labels: `python src/calibrate.py --compare-preliminary <adjudicated.csv> data/calibration/pilot/KEY_DO_NOT_OPEN.csv`, and report.

### Task C: Freeze and main run (~$20) [ask the owner first]
1. Ask the owner for the open decisions in `HANDOFF_PHASE1.md`:
   - GSM-IC in `partitions`? If yes: `python src/fetch_data.py --gsmic`, add `ext_gsmic`, about 48 more items to label.
   - Cascade λ, μ (or the frontier only).
2. Freeze the config. `run_phase1.py` writes `config.frozen.yaml` into the run folder; record its SHA-256 in the handoff.
3. `make phase1` (`CFG=config.anthropic.yaml`). Steps: generate → ablation (realistic prompt on 100 main) → baseline → verify → repair → verify_repairs → sheets → ledger. It is resumable via `.done/` markers; `--from/--until` reruns parts.
4. Watch for:
   - API errors and refusals: rows with `status`/`stop_reason`. A safety-classifier block once hit Sonnet on this task; report it, don't work around it.
   - Parse errors.
   - Cost against the $30 cap.
   - If over budget, scope down in this order: external sets to 6 + 6, then the realistic condition to 60 problems, then drop the program layer.
5. `make variance`: 20 sources × 4 conditions regenerated; flip rates.
6. Sheets land in `data/annotations/anthropic-v1/{sheet_A,sheet_B,KEY_DO_NOT_OPEN}.csv`. A labels everything, B labels a 30% stratified subset. Tell the owner the counts and estimated hours (1.5 min per item).
7. **Before committing run outputs, check licences.**
   - Real-run folders are *not* gitignored, but rows for partitions `ext_gsm1k` and `ext_gsmic` contain text derived from datasets with no declared licence.
   - Do not commit those rows. Either add a `.gitignore` rule and write those partitions to separate files (preferred: a small change in `collect_outputs.py`, with a test), or keep the whole run folder local and commit only the ledger, analysis CSVs and sheets without GSM1K/GSM-IC text.
   - Ask the owner which option they prefer.
   - Verify with `git check-ignore` and `grep` before committing. Update the handoff.

### Task D: Analysis on real labels [after adjudication into `data/annotations/anthropic-v1/adjudicated.csv`]
1. Run, in order:
   ```
   make evaluate
   make report
   make conformal
   make cascade
   make ppi
   make policy
   python src/distill.py --run data/outputs/anthropic-v1
   python src/failure_gallery.py --run data/outputs/anthropic-v1 \
       --labels data/annotations/anthropic-v1/adjudicated.csv --key data/annotations/anthropic-v1/KEY_DO_NOT_OPEN.csv
   ```
   Each writes `data/outputs/anthropic-v1/analysis/*.csv`.
2. Check each method's gate (`docs/plan/PHASE2.md`):
   - Conformal: report the whole α vs. review-rate curve and quote LTT for "of what we pass ≤ α unsafe". Per-condition rows are descriptive.
   - Cascade: report the Pareto frontier.
   - PPI: the main study is fully labelled by A, so PPI equals classical there. Use the budget curve, and use PPI for external tools.
   - Policy (bandit): only if ≥ 2 arms differ on SAFE_AND_USEFUL. State that the direct method is exact with full-information logs.
3. Red-team (`make redteam`, about $2, ask first) only if labels finish by about Nov 22. Outputs stay in `redteam/` and never enter the main sheets.
4. Flag for the owner that the statistical interpretation should be reviewed on a stronger model (Opus) before numbers are quoted.

### Task E: Real-world pieces
- **External classroom-tool audit:**
  - Follow `docs/external_collection_protocol.md`: manual capture only, after a terms-of-service check per tool. The owner and teammate do the capturing.
  - You load captures with `src/import_external.py` (`data/external/*.csv` from `TEMPLATE.csv`), verify them, and build sheets (about 30 labels per tool, sized with PPI).
  - Tool outputs are never redistributed.
- **Teacher survey:** `docs/survey/teacher_prompt_survey.md` and `src/realistic_prompts.py`. This is pending a CUHS determination; don't collect data without the owner's go-ahead.
- **Demo:** `demo/app.py` (`make demo`). Wire the policy panel once `analysis/policy.csv` exists (see `demo/README.md`). Add a test.

### Task F: Cross-family run [when OpenAI/Gemini keys exist]
- `config.example.yaml` (run_id `main-v1`): gpt-6-luna + gemini-3.8-flash as rewriters, Sonnet as critic.
- Re-check model IDs and prices first; `docs/model_selection.md` marks some as [snippet].
- Same pipeline. Combine both runs into a 4-generator comparison in the report.

### Task G: Write-up and release [final week]
- Fill `docs/final_report.md` from `analysis/*.csv`; every number must trace to a CSV.
- Run `make release` (licence rules in `docs/plan/PHASE4.md`; `test_release_excludes_gsm1k_text` must pass) and regenerate checksums.
- Update `docs/REPRODUCIBILITY.md`.
- Write `docs/plan/HANDOFF_PHASE4.md` and the final CHANGELOG entry.

## 4. How to report back
After each task:
- State what changed: files, tests added, the test count.
- Give real-API cost from the ledger.
- Give the new numbers, with caveats.
- List what's blocked and on whom.
- Give the commit SHA pushed to `dev-phases`.

Keep messages short and plain. Ask only when a decision genuinely belongs to the owner: spending, the GSM-IC inclusion, cascade weights, which tools to audit, survey/CUHS, or merging to `main`.

## 5. Useful commands
```bash
make test                                    # all offline tests
python src/run_phase1.py --config config.anthropic.yaml --mock --until report --force   # offline end to end
python src/run_phase1.py --config config.anthropic.yaml --from verify --until sheets    # partial real rerun
python src/verify.py <gens.jsonl> --config config.anthropic.yaml [--layers det]          # verify a file
python src/ledger.py --run data/outputs/anthropic-v1 --config config.anthropic.yaml      # cost
python src/report.py --run data/outputs/anthropic-v1                                     # report (works without labels)
```
