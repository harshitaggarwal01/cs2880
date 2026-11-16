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

**Update, Nov 15 (night):**
- **Calibration complete.** Both annotators labelled the 70 items blind. On SAFE: κ 0.79, AC1 0.89, 93% raw, so the target is met. Table: `data/calibration/pilot/agreement_A_vs_B.md`.
  - Every SAFE disagreement runs one way: A unsafe, B safe, 5 of A's 18.
  - "adaptation needed" (AC1 0.46) and presentation (AC1 0.53) miss the bar and get revised before the rubric freeze.
  - Next: adjudication (`src/adjudicate.py`).
- **OSCAR free tier.** Final dev pilot passed the gate (job 9153208); the main run has been running since 20:59.
  - Primary critic Qwen 32B: SAFE on 50 of 50 dev rewrites, so every flag came from the rules or the program check.
  - Llama 3B critic: unsafe on 45 of 50.
- **Paid critics prepared.** Claude Haiku/Sonnet 5.5 and GPT-6 Luna / GPT-6.1 Sol via OpenRouter, on the same rewrites with no new labels.
  - Files: `config.ollama-paid.yaml`, `scripts/paid_critics.{py,sbatch}`.
  - About $17 upper bound under a $30 cap.

**Update, Nov 16:**
- First human labels (annotator A, preliminary): careful prompts 92% SAFE vs the realistic prompt 30%.
- The AI labeller agreed with the human 93% of the time (κ 0.79) but missed 5 of 18 unsafe rewrites.
- Free tier on OSCAR via Ollama ($0), on branch `oscar-free-tier`.

**Update, Nov 15:**
- Option 2 is chosen and built: three rewriters (Haiku, Sonnet, Qwen), every critic on every output, and lean labelling, about 850 items and about 14 h per annotator.
- Cost controls are in place: an estimator, a hard cap, and budget/mid/full checker tiers. The budget tier (≈ $7.2) fits the current $9.
- All future-method modules are coded, with 221 tests passing.
- No paid runs yet; the keys are pending.
- The critical path is the 70-item calibration labelling.

**Earlier status:**

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

All of these are planned to be **coded now with synthetic tests** and run on real data once labels exist (Tasks A2 and H in `docs/plan/AGENT_PROMPT_NEXT.md`).

**Model matrix with an open model (before the main run):**
- Add a cheap open-weight **Qwen** model, via an OpenAI-compatible host or run locally, as a third rewriter and as a critic.
- Run **every available critic on every rewrite**: Opus, Sonnet, Qwen, and GPT/Gemini when keys exist. Critics reuse the same human labels, so this costs API dollars only.
- What it answers:
  - Is a free model a school could run as safe as paid ones?
  - Can a free critic pre-filter for the expensive one?
  - How large is the same-family self-preference bias? It becomes measured, not just disclosed.

**Methods, coded now:**

| Module | What it does |
|---|---|
| `policy_online.py` | Live contextual bandit (Thompson sampling, LinUCB) with a replay simulator, plus off-policy evaluation (IPS, SNIPS, doubly robust) for future logged deployments; a teacher-feedback hook in the demo |
| `audit_game.py` | Stackelberg audit game: how a district or platform should spread a limited audit budget across tools and conditions (multiple-LPs SSE, a robust variant), vs. uniform and proportional allocation. A policy simulation |
| `train_checker.py` | Small open checker: a CPU classifier on features + embeddings; an optional LoRA fine-tune of a small Qwen judge on GPU |
| `critic_ensemble.py` | Dawid–Skene: estimates each critic's accuracy without labels; a label-free UNSAFE score for PPI and conformal |
| `redteam.py --rounds` | Iterated attacker vs. checker, with a held-out attack set |
| `conformal.py` (weighted) | Carries the PASS guarantee to a new tool's outputs under distribution shift |
| Adapters | Multilingual (translate + simplify), science word problems, hint-level settings (practice vs. assessment) |
| `STUDENT_STUDY.md` | Design only: the differential-boost study (needs IRB and a school partner) |

**Considered and not pursued:**
- Restless bandits: they fit decisions about people over time, not about problems.
- Mechanism design: there is no strategic behaviour to model here.
