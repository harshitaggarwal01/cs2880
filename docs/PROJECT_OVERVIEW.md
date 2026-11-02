# SafeAdapt-Math: Project Overview (structure, methods, code, future)

*Quick reference, updated Nov 2, 2026. Branch `dev-phases`.*

## 1. What the project does

AI tools rewrite math word problems for students with disabilities, as plain language or broken into chunks. We measure whether those rewrites keep the **same math** and avoid **leaking the answer or strategy**, and we build a checker that catches the bad ones.

- **Fidelity:** same numbers, relations and question.
- **Leakage:** no added steps, operations or derived values.
- **Accommodation vs. modification:** a safe rewrite changes how the problem is presented, not what is assessed.

## 2. Study structure

| Piece | Details |
|---|---|
| **Sample** (frozen, seed 2880) | 10 dev (GSM8K train, used for tuning only) · 100 main (GSM8K test, stratified by number of steps × relational cue) · 12 ASDiv · 12 GSM1K. Optional: 12 GSM-IC distractor problems (off by default) |
| **Conditions** | 2 generators × {plain_v1, chunked_v1} on all problems · realistic teacher prompt (naive_v1) on the 100 main · deterministic non-AI split (baseline) |
| **Models** (run `anthropic-v1`) | Generators: Claude Haiku 5.5, Sonnet 5.5 · critic and extractor: Opus 5.5 (same family; disclosed). Cross-family run `main-v1` (GPT + Gemini) is a config swap |
| **Checker** | Layer 1, deterministic rules (free) → Layer 2, AI critic → Layer 3, extract each problem as a program and recompute the answer → PASS / REVIEW / REJECT |
| **Repair** | One constrained repair pass on REVIEW/REJECT, then re-verified |
| **Ground truth** | Blind human labels: annotator A labels everything, annotator B labels 30%, then adjudication. Rubric calibrated on 70 items first (κ/AC1 ≥ 0.7) |
| **Endpoints** | SAFE (fidelity and no leakage) and SAFE_AND_USEFUL (also more readable) |
| **Analysis** | Rates with source-clustered bootstrap CIs; exact McNemar + Holm within 3 prespecified families; Wilcoxon for presentation vs. baseline; exploratory logit with Firth fallback; verifier recall vs. review rate per layer; repair outcomes |

## 3. Methods ("more than a prompt")

| Method | Question it answers | File | Status |
|---|---|---|---|
| **Guaranteed PASS**: conformal risk control + Learn-then-Test | "Of what we pass, at most α is unsafe," with probability ≥ 1−δ | `src/conformal.py` | Coded, reviewed, synthetic tests |
| **Cost-aware cascade** | The cheapest order of rules → critic → program → human for a given safety level; reports the Pareto frontier | `src/cascade.py` | Coded, synthetic tests |
| **Prediction-powered inference (PPI / PPI++)** | Unbiased failure rates from a few human labels plus the cheap verifier on everything; sets the label budget for tool audits | `src/ppi.py` | Coded, fixed in review (coverage ≈ 95%) |
| **Offline contextual bandit** | Which rewrite style (or the non-AI split) to use for which kind of problem; a readable depth-2 tree, leave-source-out evaluation, Thompson replay | `src/policy.py` | Coded, synthetic tests |
| **Red-team** (stretch) | Can an attacker leak hints subtly and still pass? Recall under attack; outputs quarantined | `src/redteam.py`, `prompts/attacker_v1.txt` | Coded, synthetic tests |
| **Distilled free layer** (stretch) | How much of the critic's recall can the free features recover? | `src/distill.py` | Coded |

Method notes with citations: `docs/methods/{conformal,cascade,ppi,policy,redteam,distill}.md`.

## 4. Repo map

```
config.anthropic.yaml   Anthropic-only run (anthropic-v1)     config.example.yaml  cross-family run (main-v1)
Makefile                make test | calibrate | pilot | phase1 | evaluate | report | conformal | cascade | ppi | policy | demo | release
prompts/                plain_v1, chunked_v1, naive_v1 (realistic), critic_v1, extract_v1, repair_v1, attacker_v1
schemas/                annotation_schema.json (label fields and allowed values)
data/frozen/            frozen sample + MANIFEST      data/outputs/<run>/  generations, verify, repairs, ledger, analysis
data/calibration/pilot/ 70-item calibration sheets    data/annotations/<run>/  blind sheets + adjudicated labels
pilot/                  first 70-output pilot (preliminary labels)
demo/                   Streamlit demo (offline over a run; live with a key)
tests/                  108 offline tests, including a mock end-to-end run
docs/                   dossier, explainer, plan/, methods/, check-in note, decks
```

`src/` by stage:

| Stage | Files |
|---|---|
| Data | `fetch_data.py` (download + checksums, `--gsmic`), `sample.py` (freeze sample), `common.py` (paths, hashing, tags) |
| Generate | `llm.py` (provider wrappers: Anthropic / OpenAI / Google / mock, full logging), `collect_outputs.py` (all source × generator × transformation, resumable), `baseline.py` (non-AI split) |
| Verify | `deterministic_checks.py` (layer 1), `verify.py` (extraction cache, program check, critic, `decide`, `decide_subset` for offline ablations) |
| Repair | `repair.py` |
| Label | `make_annotation_sheets.py` (blinded A/B sheets + key), `calibrate.py` (calibration sheets, agreement, disagreement lists) |
| Run | `run_phase1.py` (one command: fetch → pilot → generate → ablation → baseline → verify → repair → verify_repairs → sheets → ledger → evaluate → report; `.done/` markers, `--mock`) |
| Analyse | `evaluate.py`, `report.py` (markdown + figures), `ledger.py` (cost per call/stage/condition), `variance_check.py` (regeneration flip rate) |
| Methods | `conformal.py`, `cascade.py`, `ppi.py`, `policy.py`, `redteam.py`, `distill.py` |
| Real world | `import_external.py` + `data/external/TEMPLATE.csv` (manual classroom-tool captures), `realistic_prompts.py` (teacher-survey prompts) |
| Release | `release.py` (licence-aware bundle: no GSM1K text, no tool outputs), `failure_gallery.py` |

## 5. Status

- **Done:**
  - All code above; 108 tests pass; the mock pipeline runs end to end.
  - Statistical review done (PPI split fixed, Firth fallback for the logit, conformal wording).
  - **Real pilot:** 40 rewrites, 17 PASS / 22 REVIEW / 1 REJECT, 40/40 answers match, $1.19.
- **Found:**
  - Two checker false-alarm sources: the "relations differ" rule is too strict, and counting words ("three ways") are read as derived values.
  - One real catch by the critic: bullets detached "from her weekly earnings" from the 5%.
- **Next:**
  1. Tune the two rules on the dev problems only.
  2. Calibration relabel, then freeze the rubric.
  3. Main run (~$20).
  4. Annotation.
  5. Analysis and the methods on real labels.
  6. Tool audit, report, release.

Details: `docs/plan/ROADMAP.md`, `docs/plan/HANDOFF_PHASE1.md`.

## 6. Future method plans

**This semester, after labels:**
- Run all four methods on the real labels.
- Report the guarantee curve (α vs. review rate) and the cascade Pareto frontier rather than a single point.
- Use PPI to size the classroom-tool audit (about 30 labels per tool).
- Run the cross-family generators when keys arrive.

**Future work (not this semester):**
1. **Live bandit:** learn the rewrite-style policy from real teacher feedback instead of offline labels.
2. **Small open checker:** train a small model on our labels so schools can run checking free or offline.
3. **Audit game (Stackelberg inspection):** with limited manual audits and vendors choosing how careful to be, which audit plan minimises unsafe content reaching students? In the style of Tambe-lab security games; a simulation/policy study, because vendors don't yet respond to audits.
4. **Iterated red-team:** run attacker vs. checker over several rounds to harden it.
5. **Student study:** test for a "differential boost" (safe rewrites help struggling readers more). Needs IRB and a school partner.
6. **Broader scope:** other subjects (science, reading comprehension), other languages (translate + simplify), other adaptations (read-aloud scripts, diagrams, hint levels).

**Considered and not pursued:**
- Restless bandits: they fit decisions about people over time, not about problems.
- Mechanism design: there is no strategic behaviour to model here.
