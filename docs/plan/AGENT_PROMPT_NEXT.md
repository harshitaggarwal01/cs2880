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

Then run `pip install -r requirements.txt && make test`. Expect **112 tests passing**. If not, fix that before anything else.

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
- **Other providers:** OpenAI, Gemini and open-model hosts (OpenRouter, Together, etc.) read their keys from env vars named in the config (`api_key_env`). The same secret rules apply.
  - Before sending study problems to a new host, check its data-use terms (no training on inputs where an opt-out exists) and record that in `docs/model_selection.md`.
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
- **Backups:** after every real-API step and every labelling milestone, run `make hf-backup`. It uploads to the private Hugging Face dataset repo `harshitaggarwal/safeadapt-math`, needs `HF_TOKEN` with write access in the environment, and refuses a public repo. If the token is missing, run `make hf-stage` and tell the owner.
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
Order: **A → A2 → B → C → D → E → H → F (as keys arrive) → G.** H can run in parallel once A2 is merged; its modules need only synthetic data until labels exist.

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

### Task A2: Open models and the full model matrix (code now; decide before the main run)
**Why:** the owner wants a free or cheap open model (Qwen) in the experiments, in every generator × critic combination the available keys allow.

**What it adds to the story:**
1. **Rewriter side:** does a free model that a school could run locally make more unsafe rewrites than paid frontier models?
2. **Checker side:** can a free model replace or pre-filter the expensive critic? This feeds the cost story and the cascade.
3. **Same-family bias, measured:** with critics from several families judging rewriters from several families, we can *measure* the self-preference bias (Panickssery et al. 2024) instead of only disclosing it.

**Labels decide the design:**
- Human labels attach to *rewrites*, not to critics. Every extra critic reuses the same labels and costs only API dollars.
- Every extra *rewriter* adds about 348 outputs to label (124 × 2 styles + 100 realistic), roughly 9 hours per annotator at full coverage.
- So: run **all critics on all rewrites** (cheap). Add **one open rewriter (Qwen)** to the main run.
- If the owner wants less labelling, label the open rewriter's outputs on a stratified 50% and use PPI (`src/ppi.py`) for its rates. Record that in the decision log.

**Code:**
1. **`src/llm.py`:** add an `OpenAICompatibleProvider` (`name = "openai_compat"`).
   - Spec fields: `base_url`, `api_key_env` (the name of the env var holding the key, never the key itself) and `model`. It covers OpenRouter, Together, DeepInfra, Groq, Fireworks, the Hugging Face router, and local vLLM or Ollama (`base_url: http://localhost:11434/v1`, no key).
   - Use the chat-completions API. Pass the JSON schema via `response_format={"type": "json_schema", ...}` when supported; otherwise fall back to `{"type": "json_object"}` plus the schema in the system prompt, then parse and validate.
   - Record `returned_model`, usage, stop reason and latency exactly like the other providers, and add the same one prespecified retry.
   - Register it in `PROVIDERS`. Tests use a fake HTTP client or monkeypatched SDK; no network in tests.
   - Add `openai>=…` to `requirements.txt` if it isn't already there.
2. **Model IDs and prices:**
   - Pick a current **Qwen instruct model** that is open-weight, cheap and widely hosted, plus optionally one small variant to show the "runs on a laptop" end.
   - **Verify the exact model ID, licence and per-token price** on the provider's model page at run time. Record them with the date in `docs/model_selection.md` and the config's `prices:` block. Do not guess IDs.
   - Prefer models whose licence allows research use and redistribution of outputs (many Qwen releases are Apache-2.0; check the specific one).
3. **`config.matrix.yaml`** (new run_id, for example `matrix-v1`). This replaces the single-`critic` design.
   - `generators:` all rewriters with available keys: Haiku 5.5, Sonnet 5.5, the Qwen model, and GPT/Gemini when keys exist.
   - `critics:` a *list*, for example Opus 5.5, Sonnet 5.5, the Qwen model, and GPT/Gemini when keys exist.
   - Keep a single `extractor` (Opus) so the program layer is constant; optionally add a Qwen extractor as an ablation.
   - Tag each model with `family:` (anthropic / alibaba-qwen / openai / google) for the bias analysis.
   - Keep `config.anthropic.yaml` working unchanged; old runs must still load.
4. **`src/verify.py` multi-critic:**
   - `--critic NAME` runs one named critic from `critics:` and writes `<gens>.verify-critic@NAME-det-program.jsonl`.
   - `--all-critics` loops over all of them. Det and program results are shared via the existing extraction cache, so extra critics only cost critic calls.
   - `decide()` stays per critic.
   - Orchestrator: add a `critics` step in `run_phase1.py` after `verify` that runs the non-primary critics. Repair is still driven by the primary critic only, which is prespecified; name it with `primary_critic:` in the config.
5. **`src/critic_matrix.py`** (new; runs after labels):
   - Per critic: recall, precision, review rate and cost per item against adjudicated SAFE labels, with source-clustered bootstrap CIs. Reuse `evaluate.verifier_metrics` and `cluster_boot`.
   - Generator × critic grid of the critic's SAFE rate and its error rate against humans.
   - **Self-preference test:** among human-UNSAFE items, a logit of "critic says SAFE" on a `same_family` indicator plus generator and critic fixed effects, with SEs clustered by source. Use `evaluate.logit_unsafe`'s Firth fallback logic, factored into a helper.
   - **Ensembles:** majority vote, any-unsafe, and a cost-ordered cascade (Qwen critic first, Opus only when Qwen is not SAFE). Feed the per-critic columns to `cascade.py` and `conformal.risk_score` so the cheap-critic options appear on the Pareto frontier.
   - Writes `analysis/critic_matrix.csv`, `analysis/self_preference.csv` and `analysis/critic_ensembles.csv`, plus one figure in `report.py`.
   - Tests on synthetic labels with planted self-preference.
6. **`src/ledger.py`:** price the new models (from `prices:`). Add `critic_name` and `family` columns.
7. **Budget estimate** (verify with the ledger on the dev pilot first): Qwen calls are cents. Each frontier critic on about 1,400 outputs is about $8–15. Run the **dev pilot through the full matrix first** (about $3–5, ask the owner), then the main run.
8. **Docs:**
   - `docs/methods/critic_matrix.md` with citations: Panickssery et al. 2024 (self-preference); Zheng et al. 2023 (LLM-as-judge); Verga et al. 2024 (panel of LLM judges).
   - A ROADMAP decision-log row.
   - The PHASE1/PHASE2 docs, updated.
   - The same-family caveat text, updated to say it is now measured.

**Decision for the owner before Task C:** which rewriters go in the main run (labels cost), and full vs. 50% + PPI labelling for the open rewriter.

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
3. `make phase1 CFG=config.matrix.yaml RUN=data/outputs/matrix-v1` (or `config.anthropic.yaml` if the owner declines the matrix). Then run the extra critics (`--all-critics`, Task A2). Steps: generate → ablation (realistic prompt on 100 main) → baseline → verify → repair → verify_repairs → sheets → ledger. It is resumable via `.done/` markers; `--from/--until` reruns parts.
4. Watch for:
   - API errors and refusals: rows with `status`/`stop_reason`. A safety-classifier block once hit Sonnet on this task; report it, don't work around it.
   - Parse errors.
   - Cost against the cap: $30 for the Anthropic-only design; ask the owner for a cap if the matrix adds frontier critics (expect $40–70).
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

### Task H: Code every future method now (synthetic tests now, real data later)
The owner wants every planned future approach coded, not just described. Every module follows the existing pattern:
- a module docstring with usage;
- pure functions plus a `--synthetic` CLI mode;
- tests in `tests/test_<module>.py` on planted data;
- a `docs/methods/<module>.md` with citations;
- a Makefile target;
- an `analysis/<module>.csv` output.

Nothing here may change the prespecified Phase-1 analysis; these are additional, clearly labelled analyses. Order by value:

1. **`src/policy_online.py`: online contextual bandit (live rewrite-style choice).**
   - Arms: deterministic split, plain/chunked × each rewriter, repair variants. Context: the features in `policy.py`.
   - Algorithms: contextual Thompson sampling (Bayesian logistic or Beta per leaf of the `policy.py` tree), LinUCB, and ε-greedy as a baseline.
   - Reward: SAFE_AND_USEFUL minus λ·cost, with an optional teacher-feedback signal.
   - **Simulator:** replay from the full-information label table (each problem has outcomes for every arm), in random arrival orders, reporting cumulative regret vs. the best fixed arm and vs. the oracle.
   - **Off-policy evaluation** for future logged deployments, where only the chosen arm is observed: IPS, SNIPS and doubly robust estimators with stored propensities. Validate them on the simulator by hiding non-chosen arms.
   - Demo hook: a thumbs-up/down feedback logger in `demo/app.py` writing to `data/feedback/*.jsonl` (gitignored), which the online policy can consume.
   - Cite: Li et al. 2010 (LinUCB); Agrawal & Goyal 2013 (TS); Dudík, Langford & Li 2011 (DR); Swaminathan & Joachims 2015 (SNIPS); Russo et al. 2018.
   - Tests: sublinear regret on a planted problem; OPE estimators unbiased on simulated logs; propensities stored and > 0.
2. **`src/audit_game.py`: Stackelberg audit game** (Tambe-lab style; the course's own methods).
   - Defender (district or platform) allocates a budget of B manual audits across targets: AI tools × conditions, or tool × problem type.
   - Attacker (a careless or cost-cutting vendor, or the worst-case target) picks where unsafe content goes unchecked.
   - Payoffs come from estimated unsafe rates and harm weights. Use the point estimates **and** their CIs from PPI/evaluate.
   - Solve the Strong Stackelberg Equilibrium by the multiple-LPs method (Conitzer & Sandholm 2006) with `scipy.optimize.linprog`. Include a robust variant that uses the interval uncertainty in the rates (in the spirit of Kiekintveld et al. 2013) as a max-min LP.
   - Compare against uniform allocation and proportional-to-rate allocation: expected unsafe items reaching students per 1,000, at matched audit budget.
   - Cite: Tambe 2011 (Security and Game Theory); Kiekintveld et al. 2009 (ERASER/compact security games); Conitzer & Sandholm 2006; Blocki et al. 2013 (audit games).
   - Tests: a 2-target game with a known closed-form equilibrium; the defender's utility is ≥ uniform; the LP is feasible at the budget extremes.
   - Clearly label this a **policy simulation**; vendors do not currently respond strategically.
3. **`src/train_checker.py`: small open checker.** This goes beyond `distill.py`.
   - Level 1 (CPU): a classifier on deterministic features plus sentence-embedding differences between the source and the rewrite, using a small open embedding model via `sentence-transformers` if installable, with a TF-IDF fallback. Evaluate leave-source-out against human SAFE labels; report recall at matched review rate vs. det-only and vs. the Opus critic.
   - Level 2 (GPU only, optional): LoRA fine-tune of a small open Qwen model as a SAFE/UNSAFE judge on (source, rewrite, label) triples, with `peft`/`transformers`, leave-source-out. Skip cleanly with a message when there is no GPU.
   - Also add the Qwen *prompted* critic from Task A2 as the zero-training baseline.
   - Cite: Hinton et al. 2015; Zhao, Knežević & Käser 2026; Hu et al. 2021 (LoRA).
   - Tests: synthetic separable data → recall > det-only; no source leakage across folds.
4. **`src/critic_ensemble.py`: label-free critic aggregation.**
   - Dawid–Skene EM (Dawid & Skene 1979) over the critic matrix (Task A2) to estimate each critic's confusion matrix and a posterior UNSAFE probability without labels.
   - Validate it against human labels where they exist. Use the posterior as a PPI predictor and as a conformal risk score.
   - Tests: recovers planted critic accuracies within tolerance.
5. **`src/redteam.py` iterated mode.**
   - `--rounds K`: the attacker gets the checker's verdicts from round k and tries again; the checker is updated between rounds only via the documented rule set (no peeking at the held-out set).
   - Report recall on a **held-out attack set** each round.
   - Outputs stay quarantined in `redteam/`.
   - Tests: quarantine holds across rounds; the round-k attacker sees only round k−1 verdicts.
6. **`src/conformal.py` extension: weighted conformal for new tools** (covariate shift; Tibshirani et al. 2019).
   - Add an option to reweight calibration sources by estimated density ratios (a logistic classifier of "new-tool vs. study" features) so the PASS guarantee can transfer to an external tool's outputs.
   - Opt-in flag; the default behaviour is unchanged. Tests on planted shift.
   - Get a stronger-model review before quoting.
7. **Broader scope adapters** (data plus prompts only; no new labels this semester unless the owner says so):
   - `fetch_data.py --mgsm`: the multilingual GSM8K translation set (Shi et al. 2022). **Check its licence before use.** Add a `translate_plain_v1` prompt (translate + simplify) and a `--lang` option.
   - A science-word-problem source with a permissive licence (find one, check the licence, document it).
   - `prompts/hint_levels_v1.txt` with an `allowed_help ∈ {none, cue, worked-step}` setting, plus a rubric note defining when hints are *intended* (practice mode vs. assessment).
   - Tests: the samplers are deterministic with seed 2880; partitions are kept separate from the frozen study sample.
8. **`docs/plan/STUDENT_STUDY.md`:** a design-only plan for the differential-boost study (needs IRB and a school partner): hypotheses, measures, power sketch, consent. No data collection.

**Considered and not pursued** (say so in the docs; don't code): restless bandits, which fit decisions about people over time rather than problems; mechanism design, which has no strategic behaviour to model here.

### Task F: Cross-family run [when OpenAI/Gemini keys exist]
This is now folded into Task A2. Add the GPT/Gemini rewriters and critics to `config.matrix.yaml` as keys arrive. A new rewriter added after labelling has started needs its own labelling batch (or PPI on a subset); a new critic needs none.
- Reference design: `config.example.yaml` (run_id `main-v1`), with gpt-6-luna + gemini-3.8-flash as rewriters.
- Re-check model IDs and prices first; `docs/model_selection.md` marks some as [snippet].
- The report compares all rewriters (Haiku, Sonnet, Qwen, and GPT/Gemini if added) and all critics in one table.

### Task G: Write-up and release [final week]
(Includes the Task A2 matrix and Task H analyses as clearly labelled extra sections; the prespecified Phase-1 results stay first.)
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
