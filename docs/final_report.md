# SafeAdapt-Math: final report (SKELETON)

**Status:** skeleton. Results sections hold placeholders only. Nothing below "TBD" may be filled from memory, from the pilot, or from the constructed stress cases: every number must come from the CSV named in its placeholder, and the CSV must be cited next to the number.

**Title (working):** Preserving the math while simplifying the words: auditing and verifying LLM accessibility adaptations of math word problems
**Course:** Harvard COMPSCI 2880, AI for Social Impact, Fall 2026 · **Run:** `TBD (anthropic-v1 and/or main-v1)` · **Commit:** `TBD` · **config.frozen.yaml SHA-256:** `TBD`

## How to fill this file

1. Run the analysis once on the adjudicated labels (`docs/REPRODUCIBILITY.md` section 5). All tables are written to `data/outputs/<run>/analysis/`.
2. Replace each `<!-- from analysis/... -->` comment with the table or sentence derived from that file, and keep the comment so a reader can trace the number.
3. Delete each "What this section must say" note once the section says it.
4. Run the claims check at the end of this file before the report is declared done.

## Section map

| Report section | Dossier section | Source of numbers |
|---|---|---|
| 1 Problem | 1, 2 | none (literature) |
| 2 Prior work | 4, 5 | none |
| 3 Theory | 6 | none |
| 4 Research questions | 7 | none |
| 5 Data | 8 | `data/frozen/MANIFEST.json` |
| 6 Conditions and models | 9, 10 | `config.frozen.yaml`, `prompts/` |
| 7 Annotation | 11 | `analysis/agreement.csv` |
| 8 Results | 12, 13, 14 | `analysis/rates.csv`, `families.csv`, `layer_ablations.csv`, `repair.json`, `presentation_vs_baseline.csv`, `logit.json` |
| 9 Methods | Phase 2 notes in `docs/methods/` | `analysis/conformal.csv`, `cascade.csv`, `ppi.csv`, `policy.csv` |
| 10 Cost | 15 | `ledger_summary.csv` |
| 11 Limitations | 16 | none |
| 12 Decision rules | 17 | sections 8 to 10 |
| 13 Social impact | 19 | none |
| 14 Future work | 6, 16 | none |

---

## 1. Problem and why it matters

Teachers increasingly use generative AI to make math word problems easier to read: plainer wording, shorter sentences, information in chunks. A fluent rewrite can still change what the learner is asked to do. It can drop a condition or flip a comparison (a loss of mathematical fidelity), or it can keep the numbers and do part of the reasoning for the student by naming an operation, stating an intermediate value, or marking which facts matter (instructional leakage). Both turn an accommodation into a modification of the task. The question of the report is how often this happens, whether it can be caught cheaply, and when less AI is the better answer.

The introduction should also say who is affected (learners who receive adapted versions, teachers who cannot check every variant, curriculum teams responsible for quality) and that the project is diagnosis-free: nothing here infers a learner's condition.

<!-- TBD: draft from dossier sections 1 and 2; cite the sources there (Fuchs et al. 2018, Walkington et al. 2018, vendor documentation). Do not quote pilot rates. -->

## 2. Prior work and novelty

What this section must say: the closest prior work (DFT-GEN, Norberg et al., Patel et al., Ikram et al., Zhao et al.), what each does not do, and the novelty claim restricted to what survives that comparison. State that for DFT-GEN only the abstract was read at the time of writing, unless that has changed.

<!-- TBD: table from dossier section 5; re-check every citation against CITATIONS.bib before submitting. -->

## 3. Theory: accommodation versus modification

What this section must say: an accommodation changes how a task is presented, a modification changes the construct measured; fidelity loss and leakage are both modifications; the allowed-edits list comes from the linguistic-modification literature; the differential-boost test (Sireci et al.) needs a learner study that this project does not run.

<!-- TBD: draft from dossier section 6. -->

## 4. Research questions

| RQ | Question | Section with the answer |
|---|---|---|
| RQ1 | Fidelity and leakage under constrained prompts, by model and transformation | 8.1 |
| RQ2 | Realistic teacher prompt versus constrained prompts | 8.2 |
| RQ3 | Verifier recall and the contribution of each layer | 8.3 |
| RQ4 | Whether one constrained repair converts unsafe to safe without regressions | 8.4 |
| RQ5 | LLM chunking versus deterministic chunking | 8.5 |

Primary endpoint: SAFE rate per condition. Secondary: SAFE_AND_USEFUL, each label dimension, verifier recall on unsafe items. Hypotheses are stated as hypotheses; no direction is assumed for model comparisons.

## 5. Data

What this section must say: the four partitions and why (dev, main, ASDiv, GSM1K ids, and GSM-IC if it was used), the stratification of the main sample, the seed, that the sample was frozen before any generation, and the licence and contamination caveats.

<!-- from data/frozen/MANIFEST.json (allocation, tag coverage); counts of items actually annotated: TBD after labels -->

## 6. Conditions and models

What this section must say: which generators, critic and extractor ran (copy from `config.frozen.yaml`), the prompts per condition, the logging rules (first response kept, one retry on technical error only), and the same-family caveat.

<!-- from config.frozen.yaml and prompts/ ; returned_model values actually observed: TBD from generations -->

> **Same-family caveat (required if the run is `anthropic-v1`).** Generators, critic and extractor come from one model family, so correlated errors are not controlled and judges tend to favour their own family's output. Verifier results from that run are a dry run of the method, not the cross-family audit. State which of the two designs each reported number comes from, and do not pool them.

## 7. Annotation and agreement

What this section must say: blinding, who labelled what (one annotator on everything, the second on the stratified subset), agreement before adjudication, how disagreements were adjudicated, and that the rubric was frozen before the main labels.

<!-- from analysis/agreement.csv: kappa and Gwet AC1 per label, SAFE first. TBD after labels -->

## 8. Results

All rates are source-clustered bootstrap estimates with 95% CIs (10,000 replicates). Report each component of SAFE next to the composite.

### 8.1 Fidelity and leakage rates (RQ1)

What this section must say: SAFE, MATH_OK and NO_LEAK per generator and transformation under constrained prompts, with CIs; which failure codes occur; the plain-versus-chunked and model-versus-model comparisons from the prespecified family, with Holm-adjusted p-values and stated as paired differences.

<!-- from analysis/rates.csv (outcome in SAFE, MATH_OK, NO_LEAK, SAFE_AND_USEFUL) and analysis/families.csv. TBD after labels -->

### 8.2 Realistic versus constrained prompts (RQ2)

What this section must say: the SAFE difference between the realistic teacher prompt and the constrained chunked prompt for the same sources, per model, and what the unsafe realistic replies contain (appended plans, step structure, stated values).

<!-- from analysis/families.csv (family: realistic vs constrained) and analysis/rates.csv; example gallery entries: docs/results/failure_gallery.md. TBD after labels -->

### 8.3 Verifier recall and layer ablations (RQ3)

What this section must say: recall on human-UNSAFE items with a CI for each layer subset (det, critic, det+critic, det+critic+program) at both operating points (REJECT only; REJECT or REVIEW), together with flag rate as review burden; whether recall reaches the 0.90 target; PASS read as "no problems detected under these checks".

<!-- from analysis/layer_ablations.csv. TBD after labels -->

### 8.4 Repair (RQ4)

What this section must say: unsafe-to-safe conversions, safe-to-unsafe regressions, change in presentation, and SAFE_AND_USEFUL yield per 100 requests, with the extra cost.

<!-- from analysis/repair.json (converted to a table). TBD after labels -->

### 8.5 Presentation versus the deterministic baseline (RQ5)

What this section must say: the paired difference in presentation score between LLM chunking and deterministic chunking, with CI and the Wilcoxon sensitivity check, and whether any advantage is concentrated in long or clause-dense problems (exploratory).

<!-- from analysis/presentation_vs_baseline.csv. TBD after labels -->

### 8.6 Exploratory: which problems fail

What this section must say: coefficients of the clustered logit of UNSAFE on step count, length, relational tags, dataset and condition, labelled exploratory, with no claims on small subgroups.

<!-- from analysis/logit.json. TBD after labels -->

## 9. Methods built on the labelled data

Each subsection gets one figure and a plain-language statement of the guarantee or estimate. The method notes in `docs/methods/` carry the details; do not restate them here.

### 9.1 Risk-controlled PASS (guarantee curve)

What this section must say: for each tolerance alpha, the share of items that can be passed while the stated risk bound holds, which form of the bound is quoted (conditional, LTT, for the headline), and that it holds for new problems from the same population only.

<!-- from analysis/conformal.csv. TBD after labels -->

### 9.2 Cost-aware cascade (frontier)

What this section must say: the cost versus residual-risk frontier over verifier stages and human review, the operating point chosen under the stated cost weights, and what it implies for review burden.

<!-- from analysis/cascade.csv and analysis/cascade_calibrated.csv. TBD after labels -->

### 9.3 Prediction-powered inference

What this section must say: unsafe-rate estimates that combine a large verifier-labelled set with the small human-labelled set, compared with the human-only estimate, and the budget curve for how many human labels are needed.

<!-- from analysis/ppi.csv and analysis/ppi_budget.csv. TBD after labels -->

### 9.4 Offline policy

What this section must say: the learned routing policy against fixed policies, evaluated with leave-source-out cross-validation, with regret; state that it is offline evaluation on one sample, not a deployment result.

<!-- from analysis/policy.csv and analysis/policy_regret.csv. TBD after labels -->

## 10. Cost

What this section must say: total spend by stage (generation, critic, extraction, repair), cost per 100 items, and human review time implied by the flag rate; prices are those recorded in the frozen config at run time.

<!-- from data/outputs/<run>/ledger.csv summary (release: ledger_summary.csv). TBD after run -->

## 11. Limitations and threats to validity

- **Scope.** English grade-school arithmetic word problems, two generators, one critic and one extractor. Nothing here speaks to other subjects, languages or grade levels.
- **No learner data.** No participants and no student data. We do not claim that any adaptation improves learning, and we make no claim about students with a particular diagnosis. Evidence that chunking helps specific groups in mathematics is thin; accessibility guidance supports clear language and manageable chunks as design practice, not as proven interventions.
- **Annotators are the authors.** We expected leakage going in. Mitigations were blinding, a double-annotated subset, agreement computed before adjudication and quoted evidence for every label. The residual risk of expectation bias remains.
- **Construct validity of leakage.** Whether a cue is harmful depends on the instructional goal; a scaffolded exercise may want hints. Our standard is equivalence to the original unassisted task, and we do not call hints bad in general.
- **Same-family judging.** If critic and generators share a family, the critic may be lenient toward them and errors may correlate (see section 6).
- **Model drift.** Model ids are not date-pinned. We log the returned model on every call and generated within one window, but a silent change cannot be excluded.
- **Contamination.** GSM8K is likely in training data. GSM1K and ASDiv are partial checks, not clean ones; GSM8K also has few irrelevant details, so relevance leakage had little room to appear.
- **Verifier claims.** PASS means no problems were detected by these checks. Recall has a confidence interval and is not a guarantee; the risk-controlled PASS in 9.1 holds only for the calibration population.
- **Small subgroups.** With 124 sources the intervals are wide (roughly 5 to 9 percentage points either side); rare failure types are descriptive only.
- **Pilot and stress cases.** The 70-output pilot used different models and preliminary labels, and the constructed stress cases are illustrations. Neither is quoted as a rate anywhere in this report.

<!-- TBD after labels: add any threat discovered during annotation or analysis (e.g. rubric changes, items dropped for API errors, prompts that failed to parse). -->

## 12. Decision rules and recommendations

The rules were written before the data were seen. State which row each finding triggers, quote the number that triggers it, and report an unexpected row as a finding, not as a failure of the study.

| If we find | Recommendation | Triggered? |
|---|---|---|
| Constrained adaptation rarely unsafe and verifier recall at or above 0.9 at an acceptable review rate | Gated generation is viable: constrained prompt, verifier, human review of flags | TBD after labels |
| Realistic prompting frequently unsafe | Tools must not pass raw replies to teachers; use constrained prompts, strip appended plans, or block | TBD after labels |
| Verifier recall below 0.9 | Human review of every adaptation stays necessary; the verifier is triage only | TBD after labels |
| Deterministic chunking about as good as LLM chunking on presentation | Use deterministic formatting; keep LLMs for clause-dense problems | TBD after labels |
| Repair rarely helps or regresses | Block instead of repairing | TBD after labels |
| Few failures anywhere | Report a credible negative result with intervals and shift emphasis to presentation and the realistic-prompt risk | TBD after labels |

"Use deterministic formatting" and "humans must review everything" are acceptable outcomes and are reported as such if the data point there.

<!-- from sections 8 to 10 once filled -->

## 13. Social-impact statement

What this section must say: who could be harmed by an unverified adaptation (learners given a different or easier task, teachers who trust a tool), who benefits if verification works, the risk that an automated PASS is over-trusted, the workload shifted to teachers by review, and that the system never infers a diagnosis and offers adaptations as options.

<!-- TBD: draft from dossier section 19; keep it consistent with the claims policy below. -->

## 14. Future work

- A learner study testing for a differential boost (the accommodation test in section 3), which needs IRB review and is out of scope this semester.
- Cross-family replication if the Anthropic-only run was the main one, and a wider set of generators.
- Other subjects, languages and grade bands; problems with more irrelevant information.
- Teacher-facing evaluation of the review workflow, including the survey instrument and external-tool audit prepared in Phase 3.

## References

<!-- TBD: build from CITATIONS.bib; include only works actually cited above. -->

## Appendices

- **A. Prompts.** `prompts/*.txt` with SHA-256 values from the generation log. <!-- TBD: inline listing -->
- **B. Rubric.** `docs/annotation_guide.md` and `schemas/annotation_schema.json` at the frozen version. <!-- TBD: version/hash -->
- **C. Failure gallery.** `docs/results/failure_gallery.md`, built by `python src/failure_gallery.py`. <!-- TBD after adjudication -->
- **D. Release.** Contents and licences of `data/release/` (`LICENSES.md`, `MANIFEST.json`).

---

## Claims check (run before submitting)

- [ ] No statement says an adaptation improves learning, or helps a diagnosis group.
- [ ] Every use of PASS means "no problems detected under these checks (at guarantee level alpha, if stated)", never "equivalent".
- [ ] No pilot number and no stress-case result is given as a rate.
- [ ] Every number in sections 7 to 10 has a placeholder comment naming its analysis file, and the file exists in `data/outputs/<run>/analysis/`.
- [ ] Results from `anthropic-v1` and `main-v1` are never pooled, and the same-family caveat is stated wherever the former is used.
- [ ] GSM1K and GSM-IC text appear nowhere in the report or the gallery.
