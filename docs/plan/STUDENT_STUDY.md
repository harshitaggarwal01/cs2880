# Student study plan: differential boost (design only)

Status: design only. No data collection, no recruitment, no contact with schools or students until CUHS approval and a school partner agreement exist. This semester's work (the audit of rewrites) does not depend on this study.

## Question
Do safe adaptations (those that pass the SafeAdapt-Math checker: same math, no leakage) help students who need them more than they help other students? That is a differential boost: the benefit of the adapted version is larger for students with reading or attention difficulties than for students without.

## Hypotheses
- **H1 (main, interaction):** the adapted-minus-original gain in accuracy is larger for the difficulties group than for the comparison group.
- **H2 (simple effect):** in the difficulties group, accuracy on adapted items is higher than on original items.
- **H3 (no harm):** in the comparison group, adapted items are not worse than original items by more than a prespecified margin (non-inferiority, margin set before data, for example 5 percentage points).
- **H4 (secondary):** time to first response and self-rated difficulty are lower on adapted items, more so in the difficulties group.
- **Exploratory:** unsafe adaptations (leakage, fidelity failures) change accuracy in the direction predicted by the leaked content. This is shown only on items already judged unsafe by human labels, and only with a pre-agreed ethical plan (students are never shown items known to be wrong or leaking; see Risks). The default is to omit this.

## Design
- Within-subject, counterbalanced. Each student sees every problem once, in either the original or the adapted form. Forms are assigned by a Latin-square order over two or more item sets, so each problem appears in both forms across students and each student gets about half in each form.
- Items: GSM8K-style problems at a grade-appropriate difficulty, with adapted versions that passed the checker and were human-verified as SAFE (fidelity PASS, leakage 0). Same answers by construction. Each item has a single numeric answer.
- Groups: students with documented reading or attention difficulties (for example an IEP or 504 plan identifying dyslexia or ADHD, as reported by the school, not diagnosed by us) versus students without. Group membership is supplied by the school in coded form; we do not collect diagnoses.
- Control for ability: a short, untimed prior-attainment measure (school math score or a brief screener) as a covariate; reading fluency screener to describe the sample.
- Setting: school computer lab or tablets, one session of about 30 minutes, supervised by school staff. No hints or tutoring in this study (`allowed_help = none`).

## Measures
- Primary: item accuracy (0/1) per student per item.
- Secondary: response time, self-rated difficulty (3-point faces scale), item skips.
- Covariates: grade, prior math attainment, reading fluency screener, form order, item set.
- Process: for adapted items only, a one-question "was anything confusing?" free text, coded blind.

## Analysis (prespecified)
Mixed-effects logistic regression: correct ~ form x group + covariates + (1 | student) + (1 | item), with the form x group coefficient as the H1 test. Report effect sizes with confidence intervals; H3 by a one-sided non-inferiority bound. Item and student random effects keep inference at both levels. Holm correction across H1 to H3. Analysis script and sample-size justification registered before data collection.

## Power sketch (assumptions, not estimates of real effects)
Assumed: 12 items per form per student (24 items total), baseline accuracy about 0.60 on original items in the comparison group, a gain of 0.02 from adaptation in the comparison group and 0.10 in the difficulties group (so a differential of 0.08), item-level intraclass correlation within student about 0.2, and a design effect from clustered items of about 1.5 (a conservative placeholder for item variance).
- With these numbers, about 80 students per group (160 total) give roughly 80% power for the interaction at alpha = 0.05 under a simple simulation; a smaller differential of 0.05 needs about 200 per group.
- Recruiting the difficulties group is the bottleneck. If only 40 per group are available, the study is underpowered for H1 and should be framed as estimating the differential with a wide interval.
- Action before IRB submission: replace this sketch with a simulation using pilot variance and the actual item count; the numbers above are placeholders.

## Consent and assent
- Parental permission (written, or an opt-out only if CUHS and the school district approve it) plus child assent in age-appropriate language. Assent screen read aloud for students with reading difficulties; the study can be stopped by the student at any time with no penalty.
- No identifiers in study data: the school keeps the linking key; we receive a study code, grade, group code and item responses.
- Results are never reported to teachers or parents per student; the school receives aggregate results only.
- Participation is not graded and does not affect any school record.

## IRB and partner requirements
- Harvard Committee on the Use of Human Subjects (CUHS) review. Likely category: research with children in an educational setting, which may qualify for expedited or exempt review under the educational-practices categories; that determination belongs to CUHS, not to us.
- Required before contact: CUHS approval; school or district research approval; a signed data-use agreement; FERPA-compliant handling of any school records (school-side linkage only); CITI training for all study staff; a named faculty sponsor.
- School partner provides: a supervising teacher or staff member, devices, the coded group list, a quiet room, and a contact for parent communication.
- Data: stored on Harvard-approved, access-controlled storage; no student text leaves the secure environment; no use of third-party LLM APIs on student responses.

## Risks and mitigations
- Stigma or labelling by group: group is coded, never shown to students or teachers in results.
- Frustration on harder items: untimed, skippable items, friendly language, stop at any time.
- Showing students items that are unfair: only human-verified SAFE adaptations are used; unsafe adaptations are never shown to students.
- Teaching-to-the-test or cheating: items are not graded; no feedback on correctness beyond the session if the school requests it.
- Confounding: group differs in prior attainment; handled by the covariate and the within-subject design, but not removed.
- Small and unrepresentative sample: results are described as estimates for the participating schools.

## What we will not claim
- That adapted problems improve learning or long-term outcomes. This study measures performance on a one-time task.
- Causal claims about disability categories or diagnoses (groups are school-reported and heterogeneous).
- That AI tools are safe in general, or that the checker guarantees safety in classrooms; it applies to the audited tools and sample.
- A differential boost if the interaction CI includes 0; null and small results are reported as such.
- That a hint or tutoring mode is evaluated here. Hint levels (`prompts/hint_levels_v1.txt`) are out of scope.
- Anything about students outside the participating schools and grades.

## Open items for the owner
Faculty sponsor and school partner; CUHS category; item set size and grade band; registration venue (OSF); whether an opt-out consent model is acceptable to the partner district.
