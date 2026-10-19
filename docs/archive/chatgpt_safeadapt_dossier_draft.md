# SafeAdapt-Math
## Verifying LLM-Generated Accessibility Adaptations of Math Word Problems

**Harvard CS 2880 — AI for Social Impact**  
**Project dossier | October 2026**  
**Status:** Proposed research design; experiments not yet run

---

## 1. Executive summary

### The problem

Mathematics word problems test more than arithmetic. Learners must also interpret language, track quantities, understand relationships, and organize information. Dense wording and presentation can create barriers for students whose mathematical understanding is stronger than their ability to process a particular form of text.

This motivates offering alternative versions of the same problem: shorter sentences, simpler non-mathematical vocabulary, or information separated into manageable chunks.

Large language models (LLMs) could help teachers produce these alternatives at scale. But rewriting creates a risk: a model might omit a condition, change a mathematical relationship, introduce ambiguity, or reveal a step the student was supposed to discover.

A rewritten problem can sound clearer while no longer testing the same mathematical task.

### Proposed project

**SafeAdapt-Math** will investigate whether LLMs can produce plain-language and chunked versions of existing math word problems while preserving mathematical meaning and instructional demand.

We will compare two LLMs and a deterministic formatting baseline, manually annotate the results, and evaluate a lightweight verifier that flags unsafe adaptations. We will then test whether one constrained revision step improves the proportion of safe, useful outputs.

### Main research question

**Can a hybrid verification and revision pipeline make LLM-generated accessibility adaptations of math word problems more mathematically faithful and instructionally safe than generation alone?**

### Intended deliverables

1. A reproducible benchmark of original problems and generated adaptations.
2. A human-annotated dataset of mathematical-fidelity and instructional-leakage judgments.
3. A taxonomy of adaptation failures.
4. A lightweight verifier with PASS, REVIEW, and REJECT decisions.
5. An evaluation of verifier-guided revision.
6. A small demonstration showing successful and unsafe adaptations.
7. A final research report explaining when generative rewriting is useful and when deterministic formatting is preferable.

**What we are not claiming:** This project will not establish that the rewrites improve learning outcomes or are effective for any specific neurodevelopmental diagnosis. It studies an important prerequisite for responsible educational deployment: preserving the original learning task.

---

## 2. The concrete examples we should show the professor

**Evidence warning:** The following are **manually constructed examples for explaining the research problem and developing the annotation rubric**. They are not measured failures from GPT, Claude, Gemini, or any other tested model. We must run the actual experiments before attributing failures or success rates to specific models.

### Example 1 — A correct accessibility adaptation

**Original problem**

> A school store sold 24 notebooks on Monday. On Tuesday, it sold twice as many notebooks as it sold on Monday. Six of Tuesday's sales were returned. How many notebooks counted as sales across both days after the returns?

**Faithful plain-language version**

> The school store sold 24 notebooks on Monday. On Tuesday, the store sold twice the number it sold on Monday. Six notebooks sold on Tuesday were returned. How many notebooks did the store sell in total after subtracting the returns?

**Faithful chunked version**

- Monday: The store sold 24 notebooks.
- Tuesday: The store sold twice as many notebooks as on Monday.
- Returns: Six notebooks sold on Tuesday were returned.
- Question: How many notebooks were sold across both days after the returns?

**Underlying mathematical structure:** 24 + (2 × 24) − 6 = 66.

**Evaluation:** Both adaptations preserve the quantities, comparison relationship, return condition, and requested answer. Neither explicitly tells the learner which arithmetic operations to perform.

**Why it matters:** This is what we want the system to achieve: a clearer presentation without changing the mathematical task.

### Example 2 — A missing condition

**Original**

> A school store sold 24 notebooks on Monday. On Tuesday, it sold twice as many. Six Tuesday sales were returned. How many notebooks counted as sales after the returns?

**Unsafe adaptation — constructed example**

> The store sold 24 notebooks on Monday. On Tuesday, it sold twice as many notebooks. How many notebooks did it sell in total?

**What went wrong:** The six returns disappeared.

**Original answer:** 66.  
**Rewritten answer:** 72.

**Failure label:** `COND_OMIT`, `ANSWER_CHANGED`.

**What a verifier should detect:** The source contains a return condition involving six notebooks, but the adaptation does not.

### Example 3 — Same numbers, different mathematics

**Original**

> Omar has three times as many stickers as Lena. Lena has 8 stickers. How many stickers does Omar have?

**Unsafe adaptation — constructed example**

> Omar has three more stickers than Lena. Lena has 8 stickers. How many stickers does Omar have?

**Original answer:** 24.  
**Rewritten answer:** 11.

**Failure label:** `REL_CHANGE`.

**Why this example is especially important:** A basic number-preservation checker would see the same numbers, 3 and 8, and might pass the rewrite. The error is in the relationship: **multiplicative comparison** became **additive comparison**.

This is one reason a mathematical-semantic verifier must go beyond matching numeric literals.

### Example 4 — Mathematical answer preserved, but solution leaked

**Original**

> An auditorium has 18 rows with 24 seats in each row. Twelve seats are broken. How many usable seats are there?

**Unsafe adaptation — constructed example**

> There are 18 rows and 24 seats in each row. First multiply 18 by 24. Then subtract the 12 broken seats. How many usable seats remain?

**What went wrong:** The rewrite explicitly gives the solution procedure.

**Original and rewritten answer:** 420.

**Failure label:** `HINT_OPERATION`.

**Why this matters:** The mathematics is unchanged, but the instructional demand is not. If the purpose is to assess whether students can identify the required operations, the rewritten version has compromised the assessment.

This is why we need **instructional fidelity**, not just mathematical equivalence.

### Example 5 — An intermediate answer is revealed

**Original**

> A theater sells 15 tickets in each of 8 rows. Twenty tickets are canceled. How many tickets remain sold?

**Unsafe adaptation — constructed example**

> The theater sold 120 tickets before cancellations. Twenty were canceled. How many remain sold?

**What went wrong:** The adaptation has performed the first multiplication for the learner.

**Original and rewritten final answer:** 100.

**Failure label:** `HINT_INTERMEDIATE`.

**Interpretation:** This could be appropriate in a different scaffolded learning activity, but it is not a faithful alternative presentation of the original unassisted problem.

### Example 6 — Unit substitution

**Original**

> A ribbon is 12 feet long. Four feet are cut off. How many feet remain?

**Unsafe adaptation — constructed example**

> A ribbon is 12 meters long. Four meters are cut off. How many meters remain?

**What went wrong:** The unit changed.

**Failure label:** `UNIT_CHANGE`.

**Why it matters:** The numeric answer remains 8, so answer-only checking fails to catch the changed physical quantity.

### Example 7 — A quantifier changes

**Original**

> Each of the 5 students receives 3 pencils. How many pencils are given out?

**Unsafe adaptation — constructed example**

> Some of the 5 students receive 3 pencils each. How many pencils are given out?

**What went wrong:** “Each of the five” became “some of the five.”

**Failure label:** `QUANTIFIER_CHANGE`, `AMBIGUITY`.

**Why it matters:** The rewritten problem no longer has enough information for a unique answer.

### Example 8 — An unnecessary rewrite

**Original**

> Sam has 7 apples. Sam buys 2 more apples. How many apples does Sam have now?

**Unnecessary adaptation — constructed example**

> Sam possesses seven apples and subsequently acquires an additional two apples. What is Sam's resulting total quantity of apples?

**What went wrong:** The original was already short and clear. The adaptation made it harder to read.

**Failure label:** `OVER_SIMPLIFY`, `PRESENTATION_WORSE`.

**Desired behavior:** The system should be allowed to return **NO_REWRITE_NEEDED**.

### Summary of the example types

| Example | Mathematical fidelity | Instructional fidelity | Presentation quality |
|---|---|---|---|
| Faithful plain-language rewrite | Pass | Pass | Improved |
| Faithful chunking | Pass | Pass | Improved |
| Missing return condition | Fail | Fail | May appear improved |
| “Three times” becomes “three more” | Fail | Fail | May appear improved |
| Explicit operation hint | Pass | Fail | Possibly improved |
| Intermediate answer revealed | Pass | Fail | Possibly improved |
| Feet become meters | Fail | Potentially fail | Neutral |
| Quantifier changes | Fail | Fail | Ambiguous |
| Unnecessary complicated rewrite | Pass | Pass | Worse |

**Central insight:** Readability, mathematical equivalence, and instructional equivalence are three different properties. A good evaluation must measure them separately.

---

## 3. Does the research actually support our premise?

The evidence supports concern about meaning preservation in LLM simplification and establishes that math-problem rewriting is an active educational research area.

However, we should not claim that a particular LLM frequently makes each of the exact errors above unless we observe those errors or identify them explicitly in published results.

### Direct prior work: rewriting mathematics problems

**Norberg et al. (2025), _Rewriting Content with GPT-4 to Support Emerging Readers in Adaptive Mathematics Software_.**

This paper examines GPT-4 rewriting of mathematics content in Carnegie Learning's MATHia system, including readability and learner outcomes.

It establishes that LLM-based adaptation of math problems has already been investigated in a real educational context.

**What it does not automatically establish for our project:** The prevalence of our specific proposed failure types across two contemporary LLMs, two constrained formats, and a verifier-guided revision pipeline.

Source: https://doi.org/10.1007/s40593-024-00420-2

### Direct evidence of information loss in simplification

**Trienes et al. (2024), _InfoLossQA: Characterizing and Recovering Information Loss in Text Simplification_.**

The researchers examined LLM simplifications of medical research abstracts, created 1,000 linguist-curated question-answer pairs from 104 simplifications, and found that information loss and vagueness occurred frequently. They also found that automated methods struggled to identify information loss reliably according to expert standards.

**Relevance:** Strong empirical support for the broader risk that simplification can remove important meaning and that a second AI model is not automatically a reliable verifier.

**Limit:** The domain is medical text, not mathematics word problems.

Source: https://aclanthology.org/2024.acl-long.234/

### Meaning preservation is not the same as readability

**Agrawal and Carpuat (2024), _Do Text Simplification Systems Preserve Meaning? A Human Evaluation via Reading Comprehension_.**

This work examines meaning preservation using human reading-comprehension evaluation.

**Relevance:** It motivates evaluating whether a simplified text retains information rather than relying on readability scores.

**Limit:** It is not a direct estimate of math-task corruption.

Source: https://aclanthology.org/2024.tacl-1.24/

### Existing benchmarks already evaluate generated math content

**Christ et al. (2026), _EDUMATH: Generating Standards-aligned Educational Math Word Problems_.**

This ACL paper evaluates more than 11,000 generated math problems, develops teacher-annotated data, and includes a student evaluation.

**Relevance:** It is a methodological precedent for combining human and automated evaluation of educational math content.

**Difference:** EDUMATH focuses on generating customized problems. SafeAdapt-Math begins with an existing problem and requires the adaptation to preserve that particular task.

Source: https://aclanthology.org/2026.acl-long.1973/

### The actual evidence gap

The proposed study asks a narrower question than general simplification or general math generation:

**When we require an LLM to preserve an existing mathematical task while changing only its presentation, what types of failure occur, how often do they occur, and can a conservative verification pipeline reduce them?**

That is a legitimate question even if the failure rate turns out to be low.

A low failure rate would be an informative result, not a reason to invent dramatic failures.

---

## 4. Social-impact motivation

### Who may benefit?

Potential beneficiaries include:

- Students who find dense or complex language difficult to process.
- Some neurodivergent learners who benefit from clearer organization or alternative presentation.
- Multilingual learners and emerging readers.
- Students with reading difficulties.
- Teachers who need to prepare multiple versions of instructional materials.
- Curriculum and educational-technology teams responsible for quality assurance.

These categories overlap, but they should not be treated as interchangeable.

### Why mathematics?

A student may know how to multiply, divide, or compare quantities yet struggle to extract the relevant information from a word problem.

Research on linguistic factors in mathematics supports treating language as a relevant component of word-problem difficulty.

A useful starting point is:

**Daroczy et al. (2015), _Word problems: A review of linguistic and numerical factors contributing to their difficulty_.**

https://doi.org/10.3389/fpsyg.2015.00348

Another is:

**Walkington, Clinton, and Shivraj (2018), _How Readability Factors Are Differentially Associated With Performance for Students of Different Backgrounds When Solving Mathematics Word Problems_.**

https://doi.org/10.3102/0002831217737028

These sources motivate the educational barrier. They do not establish that our generated adaptations will improve learning.

### Why neurodiversity-informed rather than diagnosis-based?

Learners with the same diagnosis can have very different preferences and needs. Some may benefit from shorter sentences, some from visual organization, some from read-aloud, and some may prefer the original wording.

Our project does not infer diagnoses or assume a universal accessibility transformation.

The system should eventually allow learners or educators to choose the representation they find useful.

The current study evaluates **whether the alternate representation is safe to offer**, not whether it is beneficial to every learner.

### The social-impact theory

The intended pathway is:

1. Some educational materials create avoidable language or presentation barriers.
2. Alternative representations may reduce those barriers for some learners.
3. Manual rewriting and checking require educator time.
4. LLMs may reduce the effort required to produce alternatives.
5. Unsafe rewriting can introduce mathematical errors or unintended assistance.
6. A verifier could help identify unsafe alternatives before they reach students.
7. Human-reviewed, safer adaptation workflows could eventually support more inclusive instruction.

The project directly tests steps 4–6. It does not yet establish step 7 or improved student outcomes.

---

## 5. Existing systems and products

| System | What it contributes | Relationship to our project |
|---|---|---|
| Carnegie Learning MATHia | Adaptive mathematics instruction; setting for published rewriting research | Closest educational prior art |
| Diffit | AI-supported differentiation and adaptation of educational resources | Example of the real-world content-adaptation workflow |
| Microsoft Immersive Reader | Reading and display supports such as spacing and line focus | Important non-generative alternative |
| MagicSchool | Teacher-facing generative AI tools | Illustrates demand for educator content workflows |
| CAST UDL Guidelines | Design framework for learner variability and multiple representations | Accessibility motivation, not proof of efficacy |
| 1EdTech AccessForAll | Preference-based accessibility concepts | Supports diagnosis-free adaptation architecture |

A key question is whether rewriting is necessary at all.

For many problems, deterministic formatting, text spacing, highlighting, or read-aloud may be safer than changing the wording.

**A successful research result could recommend deterministic formatting over LLM rewriting for certain problem types.**

That is compatible with AI for Social Impact: the goal is to improve outcomes responsibly, not maximize the amount of AI used.

---

## 6. Novelty and contribution

### What is not novel

- Asking an LLM to simplify a math problem.
- Using GPT-4 to improve readability in adaptive math software.
- Evaluating generated mathematics questions.
- Asking an LLM whether another LLM's output is correct.
- Reporting generic readability scores.

### What we propose to contribute

**A. A task-preservation benchmark**

The source problem is fixed. The output is allowed to change presentation, not the mathematical task.

**B. A two-dimensional safety analysis**

We separately evaluate:

- Mathematical-semantic preservation.
- Instructional-demand preservation.

A rewrite can preserve the final answer while leaking the method.

**C. A failure taxonomy**

We distinguish changed quantities, changed relations, missing conditions, unit errors, ambiguity, and different levels of solution leakage.

**D. A hybrid verifier**

Instead of trusting a single LLM judgment, the verifier combines deterministic checks, structured mathematical comparisons, and a fallible semantic critic.

**E. A repair experiment**

We test whether providing specific verifier feedback improves the output after one constrained revision.

**F. A deployment-oriented comparison**

We compare the quality and cost of generative rewriting against a deterministic baseline and quantify the human review still required.

**Novelty qualification:** This combination is a proposed contribution, not a claim that no related system exists. The literature review should continue through the final submission.

---

## 7. Research questions and hypotheses

### RQ1 — Baseline fidelity

How reliably do two LLMs generate plain-language and chunked versions of grade-school mathematics word problems while preserving the original task?

**H1:** The two transformation types will have different failure profiles, but we do not assume in advance which model will be safer.

### RQ2 — Failure modes

Which errors occur most often: missing information, altered mathematical relationships, new ambiguity, unintended hints, or other failures?

**H2:** Answer equivalence alone will fail to identify some unsafe adaptations.

### RQ3 — Verification

Can a hybrid verifier detect unsafe adaptations more reliably than simple numerical checks or an LLM-only judge?

**H3:** Combining complementary checks will improve unsafe-output recall, potentially at the cost of more false alarms.

### RQ4 — Revision

Does one verifier-guided revision increase strict safe-and-useful adaptation rate?

**H4:** Revision will repair some flagged outputs, but some will remain unsafe or become less readable.

### RQ5 — AI versus simpler alternatives

When does generative rewriting offer enough presentation benefit to justify its added risk, latency, cost, and review burden compared with deterministic chunking?

**H5:** Deterministic formatting will be competitive for some problems, especially those already written in clear language.

These are hypotheses to test, not findings.

---

## 8. Dataset and sampling plan

### Primary dataset: GSM8K

**GSM8K** is a benchmark of grade-school mathematics word problems with worked solutions.

The commonly distributed main split contains:

- 7,473 training problems.
- 1,319 test problems.

Official research source:

https://openai.com/index/solving-math-word-problems/

Dataset documentation:

https://github.com/openai/grade-school-math

### Planned sample

| Partition | Problems | Use |
|---|---:|---|
| Development | 10 | Prompt design, annotation rubric, verifier tuning |
| Main held-out evaluation | 100 | Primary analysis |
| External validation | 25 | Limited generalization check |
| Total | 135 | Includes development |

The external validation set could use appropriately licensed examples from GSM1K, after confirming access terms and avoiding duplicates.

GSM1K reference:

https://papers.nips.cc/paper_files/paper/2024/hash/53384f2090c6a5cac952c598fd67992f-Abstract-Datasets_and_Benchmarks_Track.html

### Sampling

A random sample alone may overrepresent common arithmetic structures.

We should stratify the 100 evaluation problems using categories such as:

- Addition and subtraction.
- Multiplication and division.
- Multiplicative comparison.
- Fractions and percentages.
- Multi-step problems.
- Time and unit conversions.
- Conditional or temporal relationships.
- Problems with potentially ambiguous referents.

The categories may overlap. We should freeze the sample before generating outputs and retain a random seed.

### Data limitations

GSM8K contains no learner accessibility preferences, reading-difficulty labels, or neurodivergence information.

It is suitable for testing **content fidelity**. It cannot directly measure whether an adaptation improves comprehension.

The dataset is also widely known to contemporary LLMs, so memorization or prior exposure may affect model behavior.

---

## 9. Experimental conditions

### Generators

Select two currently available LLMs from different model families or providers. Freeze exact model IDs before the study.

Each model receives the same source problems and two transformation instructions.

### Transformation A — Plain language

Allowed:

- Shorter sentences.
- More direct syntax.
- Familiar non-mathematical vocabulary.
- Clarification of pronouns when meaning remains unchanged.
- Removal of unnecessary narrative complexity.

Not allowed:

- Changed quantities.
- Changed units.
- Changed relationships.
- Missing conditions.
- Changed target question.
- Added arithmetic operations.
- Added intermediate or final answers.

### Transformation B — Chunked format

Allowed:

- One original fact per line.
- Clear spacing.
- Bullets.
- A visually separated question.

Not allowed:

- Step-by-step solving instructions.
- New formulas.
- Hints not present in the source.
- Reordering that changes temporal meaning.

### Deterministic baseline

Split the source into sentences and display each sentence on a separate line.

Preserve the wording, numbers, relationships, and order.

The deterministic baseline is important because it can improve visual organization without generating new semantic content.

### Output counts

For 125 evaluation problems:

| Condition | Outputs |
|---|---:|
| Model A — plain language | 125 |
| Model A — chunked | 125 |
| Model B — plain language | 125 |
| Model B — chunked | 125 |
| Deterministic chunking | 125 |
| **Total initial outputs** | **625** |

The revision experiment adds outputs only for the candidates selected for repair.

---

## 10. Generator prompts

### Plain-language prompt

**System instruction**

You are rewriting an existing grade-school mathematics word problem to make its language clearer. You are not solving it or creating a different problem.

Preserve every mathematical quantity, unit, entity, relationship, condition, temporal dependency, and the exact quantity being asked for.

Do not provide operation hints, equations, intermediate calculations, solution steps, or the answer.

Use shorter sentences and simpler non-mathematical vocabulary when helpful.

If the original problem is already clear and concise, return it unchanged and indicate that no rewrite was needed.

Return only the adapted problem and a machine-readable rewrite-status field.

**User input**

Original problem: `{problem_text}`

### Chunking prompt

**System instruction**

Reformat the following mathematics word problem into short, visually separated pieces of information.

Preserve the exact wording whenever possible. Preserve all quantities, units, mathematical relationships, conditions, and the target question.

Do not add labels such as "Step 1," "Multiply," or "Subtract." Do not solve the problem or reveal any part of the solution.

Use one given fact per line, followed by the original question.

**User input**

Original problem: `{problem_text}`

### Required generation metadata

For every output, record:

- Source problem ID.
- Source problem text.
- Model provider.
- Exact model ID.
- Generation date.
- Prompt version.
- Transformation type.
- Supported sampling settings.
- Raw output.
- Token usage.
- Latency.
- API errors.
- Estimated cost.

The reference solution must not be included in the generator prompt.

---

## 11. Annotation framework

Each generated adaptation will be compared with its source.

### Core labels

| Label | Definition |
|---|---|
| `answer_preserved` | A correct solution yields the same requested answer |
| `structure_preserved` | All mathematical relationships and conditions remain equivalent |
| `instructional_demand_preserved` | No new solution information is provided |
| `ambiguity_introduced` | The rewrite creates uncertainty absent from the source |
| `format_compliance` | The requested transformation was achieved |
| `presentation_quality` | The rewritten version is clear and well organized |
| `adaptation_needed` | The source would plausibly benefit from the requested transformation |
| `adaptation_effective` | The output meaningfully improves the intended presentation property |

### Failure taxonomy

| Code | Meaning |
|---|---|
| `QTY_CHANGE` | A numerical value changed |
| `QTY_OMIT` | A quantity disappeared |
| `UNIT_CHANGE` | A unit changed |
| `ENTITY_CHANGE` | An entity or referent changed |
| `REL_CHANGE` | A mathematical relationship changed |
| `COND_OMIT` | A condition disappeared |
| `TARGET_CHANGE` | The requested unknown changed |
| `ORDER_CHANGE` | A temporal or procedural dependency changed |
| `QUANTIFIER_CHANGE` | Words such as all, each, some, or at least changed |
| `AMBIGUITY` | New ambiguity was introduced |
| `CONTRADICTION` | The output contains incompatible statements |
| `HINT_OPERATION` | A required operation was revealed |
| `HINT_INTERMEDIATE` | An intermediate result was revealed |
| `ANSWER_LEAK` | The final answer was revealed |
| `NO_ADAPT` | The requested adaptation was not made |
| `OVER_SIMPLIFY` | Necessary meaning or useful terminology was removed |
| `FORMAT_FAIL` | The output did not follow the format request |

### Primary outcome

**Strict safe-and-useful adaptation rate.**

An output passes only if:

1. The answer is preserved.
2. Mathematical structure is preserved.
3. No new ambiguity is introduced.
4. Instructional demand is preserved.
5. The requested format is satisfied.
6. The transformation provides a meaningful presentation improvement, or correctly abstains when no rewrite is needed.

We should also report each component separately. A single composite score could otherwise conceal important failure patterns.

### Annotation protocol

One researcher codes every output.

The other independently codes approximately half, with emphasis on balanced coverage of models, formats, and mathematical structures.

Disagreements are resolved through discussion, with the original source and worked solution available to adjudicators.

Report agreement before adjudication.

For binary labels, Cohen's kappa can be used alongside raw agreement. For ordinal ratings, use an appropriate weighted agreement measure.

Because both annotators are project authors, the study should acknowledge possible expectation bias. Outputs should be presented without model identity during annotation wherever practical.

---

## 12. Technical architecture

### Pipeline

**Stage 1 — Source selection**

Load the source problem and record its ID and metadata.

**Stage 2 — Generation**

Send the source to each LLM under the plain-language and chunked prompts.

**Stage 3 — Deterministic baseline**

Produce a formatting-only version.

**Stage 4 — Verification**

Compare each candidate with the source using several complementary checks.

**Stage 5 — Decision**

Return PASS, REVIEW, or REJECT.

**Stage 6 — Constrained revision**

For flagged outputs, allow one repair attempt using explicit feedback.

**Stage 7 — Independent evaluation**

Human annotators evaluate original and revised outputs.

**Stage 8 — Analysis**

Calculate safety, quality, verification performance, cost, and failure distributions.

### Component A — Quantity and unit checker

Extract and normalize:

- Integers and decimals.
- Fractions.
- Percentages.
- Monetary amounts.
- Measurement units.
- Times and durations.

Compare source and adaptation.

A missing or changed quantity is a risk signal.

**Limitation:** Equivalent paraphrases may express a quantity differently. The checker should flag uncertainty rather than automatically reject all lexical differences.

### Component B — Entity and relationship checker

Represent key mathematical facts in structured form.

For example:

Original: "Omar has three times as many stickers as Lena."

Structured representation:

- Subject: Omar's stickers.
- Relationship: multiplicative comparison.
- Object: Lena's stickers.
- Factor: 3.

Unsafe adaptation: "Omar has three more stickers than Lena."

Extracted relationship: additive comparison.

The mismatch is a strong warning.

### Component C — Symbolic consistency checker

Where reliable formalization is possible, compare equations representing the original and rewritten problems.

Example:

Original: `24 + (2 × 24) − 6`

Adaptation with missing return: `24 + (2 × 24)`

The expressions are not equivalent.

**Important limitation:** Automatically extracting equations from natural language is itself error-prone. A solver producing the same answer does not prove semantic equivalence.

When formalization is uncertain, return UNKNOWN rather than inventing a proof.

### Component D — Instructional-leakage detector

Check whether the rewrite introduces:

- Explicit operation names.
- New arithmetic symbols.
- Equations.
- Intermediate results.
- Final answers.
- Phrases such as "first multiply" or "then subtract."

The detector must compare the rewrite with the source; an operation word already present in the original is not necessarily a newly introduced hint.

### Component E — Semantic critic

Use an independently configured LLM to compare the source and candidate.

The critic should return:

- Same quantities?
- Same units?
- Same relationships?
- Same conditions?
- Same target?
- New ambiguity?
- Added solution information?
- Evidence spans supporting any concern?

**The critic is not ground truth.** Its output is an additional signal, and its errors must be evaluated against human annotations.

### Decision policy

**PASS:** No detected mathematical or instructional changes, with sufficient agreement among checks.

**REVIEW:** Some component reports uncertainty, conflicting evidence, or a possible change.

**REJECT:** Clear mathematical corruption or explicit solution leakage is detected.

In a teacher-facing deployment, PASS should mean "no detected problems under the current checks," not "mathematically proven safe."

### Constrained repair

For REVIEW or REJECT cases:

1. Supply the original problem.
2. Supply the unsafe candidate.
3. Supply the verifier's specific concerns.
4. Request a revised adaptation addressing only those concerns.
5. Do not provide the worked solution.
6. Allow one revision.
7. Re-run verification.
8. Independently annotate the revision.

This creates a measurable intervention:

**Generation alone versus generation plus verifier-guided repair.**

---

## 13. Verifier evaluation

### Main verifier metric

**Recall on unsafe adaptations.**

Of all adaptations that human annotators determine are unsafe, what proportion does the verifier flag?

This matters because undetected unsafe outputs are the central deployment risk.

### Additional metrics

- Precision on unsafe-output flags.
- False-negative rate.
- False-positive rate.
- Specificity.
- Negative predictive value.
- Percentage of outputs requiring human review.
- Average verification latency.
- Cost per evaluated problem.
- Safe-and-useful rate after repair.

### Baselines

Compare:

1. Numeric and unit checks only.
2. LLM semantic critic only.
3. Hybrid verifier.
4. Hybrid verifier plus constrained repair.

### Leakage-safe evaluation

The verifier should be developed using the 10 development problems and any separately constructed stress tests.

Its final performance must be evaluated on the held-out sample.

Do not repeatedly tune thresholds after inspecting the final labels and then report performance on those same outputs as if the evaluation were independent.

---

## 14. Statistical analysis

### Unit of analysis

The original problem is the principal sampling unit.

Each problem produces multiple related adaptations. Those outputs are not statistically independent.

### Primary comparisons

- Model A versus Model B.
- Plain language versus chunked.
- Generative chunking versus deterministic chunking.
- Before versus after constrained repair.

### Reporting

For each condition, report:

- Number of evaluated outputs.
- Number and percentage passing each safety dimension.
- Strict safe-and-useful rate.
- Confidence intervals.
- Breakdown by mathematical structure.
- Examples of successes and failures.

### Uncertainty

Use paired comparisons and cluster-bootstrap confidence intervals by original problem.

When resampling a problem, include all its associated versions together.

McNemar tests may be used for selected paired binary comparisons.

Because the dataset is relatively small, rare failure categories should be analyzed descriptively rather than used to support strong generalization claims.

### Sample-size limitation

The four LLM conditions produce 500 outputs from 125 source problems, but this is not equivalent to 500 independent source problems.

The study can produce a useful comparative benchmark and error analysis. It cannot certify an extremely low production failure rate.

---

## 15. Professor-ready demonstration

### Two-minute demo structure

**First 20 seconds — Show the motivation**

Display a moderately dense math word problem.

Explain that some students may understand the arithmetic but struggle with how the information is presented.

**Next 30 seconds — Show a faithful adaptation**

Present the same problem with shorter sentences or chunked facts.

Highlight that all quantities and relationships are preserved.

**Next 30 seconds — Show a failure**

Display:

Original: "Omar has three times as many stickers as Lena."

Unsafe rewrite: "Omar has three more stickers than Lena."

Explain that the text appears simpler, but the mathematics changed.

**Next 20 seconds — Show instructional leakage**

Display:

Original: "There are 18 rows with 24 seats each. Twelve are broken."

Unsafe rewrite: "First multiply 18 by 24, then subtract 12."

Explain that the answer may remain correct while the assessment has been compromised.

**Final 20 seconds — Show the research question**

Ask:

"Can we automatically identify these failures, repair them, and know when a simpler deterministic formatting method is safer?"

### What the demo must disclose

The examples above are constructed illustrations.

Before the next faculty presentation, run the frozen prompts against the two selected LLMs and replace or supplement the constructed cases with actual verbatim outputs.

For every real example, show:

- Original problem and dataset ID.
- Model name and exact version.
- Prompt version.
- Generation date.
- Verbatim output.
- Human annotation.
- Why it passes or fails.

Do not cherry-pick only failures. Include a successful adaptation and an unchanged/no-rewrite case.

---

## 16. Optional educator evaluation

The core project does not require participant recruitment.

If permitted and feasible, a small educator review could improve the practical relevance of the benchmark.

### Example survey questions

For each original/adapted pair, ask educators to rate:

1. How easy is the adapted problem to read?
2. Does it preserve the same mathematical task?
3. Does it reveal a strategy students were expected to identify independently?
4. Would you be comfortable offering it to a student without editing?
5. If not, what would you change?
6. Is the adaptation actually necessary?
7. Would deterministic formatting have been sufficient?

The educator evaluation would be exploratory unless appropriately designed and powered.

If research participants are recruited, institutional requirements and approval should be checked before data collection.

A future learner study would be necessary to test whether these adaptations actually improve accessibility, comprehension, agency, or learning.

---

## 17. Ethics, safety, and limitations

### No diagnosis inference

The system will not attempt to identify ADHD, dyslexia, autism, or any other diagnosis from learner behavior or text.

### No student records required

The primary benchmark uses publicly available mathematics problems rather than sensitive student interaction data.

### No unsupported accessibility claims

The project does not assume plain language or chunking helps everyone.

### Human oversight

A production deployment should allow educators to inspect, reject, and revise generated content.

### No false certification

The verifier should not be marketed as proving mathematical equivalence. It is a risk-detection tool with measurable false negatives.

### Dataset contamination

Contemporary models may have encountered GSM8K during training. An external validation set and careful reporting are important.

### Annotation bias

Team-authored labels may be influenced by expectations. Blinding model identities and reporting disagreement can reduce, but not eliminate, this concern.

### Model variability

Model behavior can change across versions, prompts, and inference settings. The experiment must log these details.

### Social-impact limitation

A safer content-generation pipeline is not the same as demonstrated improvement in educational equity.

The project should describe its impact as enabling more responsible adaptation workflows, with learner benefits requiring future validation.

---

## 18. Implementation and repository structure

### Suggested stack

- Python for generation, parsing, evaluation, and analysis.
- Pandas for data management.
- JSON or JSONL for raw outputs and annotations.
- Pydantic or JSON Schema for structured verifier outputs.
- SymPy for limited symbolic checks.
- Scikit-learn for evaluation metrics.
- SciPy and bootstrap methods for statistical comparisons.
- A lightweight Streamlit demo if time permits.
- Git for version control.
- A pinned dependency environment for reproducibility.

### Suggested repository

- `data/source/` — original problem IDs and metadata.
- `data/generated/` — immutable model outputs.
- `data/annotations/` — human judgments.
- `prompts/` — versioned generator and repair prompts.
- `src/generate.py` — generation pipeline.
- `src/baseline.py` — deterministic formatting.
- `src/extract.py` — quantity, entity, and relationship extraction.
- `src/verify.py` — verifier logic.
- `src/repair.py` — constrained revision.
- `src/evaluate.py` — metrics and comparisons.
- `tests/` — constructed unit tests.
- `notebooks/` — analysis and figures.
- `demo/` — optional interface.
- `README.md` — setup and reproducibility instructions.

### Quality-control tests

Before the main experiment, test the verifier against known constructed cases:

- Missing number.
- Changed unit.
- Additive versus multiplicative comparison.
- Omitted return condition.
- Reversed comparison.
- Added operation hint.
- Added intermediate result.
- Answer leakage.
- Faithful paraphrase.
- Faithful deterministic chunking.
- Already-clear problem requiring no rewrite.

These unit tests are useful for software correctness but must not be presented as measured LLM failure frequencies.

---

## 19. Feasibility for a two-person team

### Minimum viable project

The minimum credible deliverable is:

- 100 held-out GSM8K problems.
- Two models.
- Two transformations.
- Deterministic chunking baseline.
- A frozen annotation rubric.
- Human evaluation.
- Failure taxonomy.
- Paired statistical analysis.
- A reproducible example gallery.

### Stronger recommended version

Add:

- Hybrid verifier.
- PASS/REVIEW/REJECT classification.
- One constrained revision.
- Before/after evaluation.
- Cost and review-burden analysis.

### Optional extensions

- External validation problems.
- Small educator review.
- Lightweight interactive demonstration.
- Additional model or prompt ablations.

### Suggested sequence

**Phase 1 — Establish the problem and examples**

Read the closest prior work, run a small number of real examples, freeze the scope.

**Phase 2 — Build the benchmark**

Select source problems, freeze prompts, collect outputs, implement deterministic baseline.

**Phase 3 — Annotate**

Apply the rubric, independently double-code a substantial subset, resolve disagreements.

**Phase 4 — Build the verifier**

Start with deterministic checks, then add semantic and instructional checks.

**Phase 5 — Test repair**

Run one revision for flagged outputs and annotate the results.

**Phase 6 — Analyze and present**

Report rates, uncertainty, failure categories, costs, examples, and limitations.

The exact schedule should be adapted to the course timeline.

---

## 20. Decision criteria

### Continue with the verifier if

- The initial benchmark reveals meaningful unsafe-output categories.
- The verifier catches errors that simpler checks miss.
- False-negative performance is informative.
- Repair improves safe-and-useful rate without excessive degradation or cost.

### Simplify the project if

- Human annotation takes substantially longer than expected.
- Semantic extraction proves too unreliable.
- The verifier creates excessive false alarms.
- The main benchmark already provides a strong, reproducible result.

### Report a negative result if

- Neither model exhibits many detectable failures.
- The verifier adds little beyond numeric checks.
- Revision makes outputs worse.
- Deterministic formatting achieves similar presentation quality with lower risk.

Negative findings are acceptable if the evaluation is credible.

---

## 21. Recommended readings

### Priority 1 — Read before finalizing the project

**1. Norberg et al. (2025). _Rewriting Content with GPT-4 to Support Emerging Readers in Adaptive Mathematics Software_.**

https://doi.org/10.1007/s40593-024-00420-2

**Why:** Closest direct prior art. Establishes what we cannot claim as new.

**2. Trienes et al. (2024). _InfoLossQA: Characterizing and Recovering Information Loss in Text Simplification_.**

https://aclanthology.org/2024.acl-long.234/

**Why:** Direct evidence of information loss in LLM simplification and limitations of automated detection.

**3. Agrawal and Carpuat (2024). _Do Text Simplification Systems Preserve Meaning? A Human Evaluation via Reading Comprehension_.**

https://aclanthology.org/2024.tacl-1.24/

**Why:** Foundation for distinguishing readability from meaning preservation.

**4. Christ et al. (2026). _EDUMATH: Generating Standards-aligned Educational Math Word Problems_.**

https://aclanthology.org/2026.acl-long.1973/

**Why:** Strong contemporary comparator for teacher-annotated math-generation evaluation.

**5. Daroczy et al. (2015). _Word Problems: A Review of Linguistic and Numerical Factors Contributing to Their Difficulty_.**

https://doi.org/10.3389/fpsyg.2015.00348

**Why:** Learning-sciences basis for treating language and mathematical structure separately.

### Priority 2 — Research design and social impact

**6. Perrault, Fang, Sinha, and Tambe. _AI for Social Impact: Learning and Planning in the Data-to-Deployment Pipeline_.**

https://crcs.seas.harvard.edu/publications/ai-social-impact-learning-and-planning-data-deployment-pipeline

**Why:** Frames the project as an intervention and deployment problem, not merely a model benchmark.

**7. CAST Universal Design for Learning Guidelines 3.0.**

https://udlguidelines.cast.org/

**Why:** Learner variability, multiple representations, and accessibility-informed design.

**8. 1EdTech AccessForAll.**

https://www.1edtech.org/standards/accessibility/index

**Why:** Preference-based accessibility architecture without diagnosis inference.

**9. Walkington, Clinton, and Shivraj (2018). _How Readability Factors Are Differentially Associated With Performance for Students of Different Backgrounds When Solving Mathematics Word Problems_.**

https://doi.org/10.3102/0002831217737028

**Why:** Empirical motivation for the relationship between language and math-problem performance.

### Priority 3 — Datasets, robustness, and generalization

**10. Cobbe et al. (2021). _Training Verifiers to Solve Math Word Problems_.**

https://arxiv.org/abs/2110.14168

**Why:** GSM8K background and mathematical verification context. Note that verifying a solution is not identical to verifying a rewritten task.

**11. Mirzadeh et al. (2024). _GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models_.**

https://arxiv.org/abs/2410.05229

**Why:** Demonstrates sensitivity in mathematical reasoning to changes in problem presentation. Solver instability alone is not evidence that an adaptation changed the task.

**12. _A Careful Examination of Large Language Model Performance on Grade School Arithmetic_ (2024).**

https://papers.nips.cc/paper_files/paper/2024/hash/53384f2090c6a5cac952c598fd67992f-Abstract-Datasets_and_Benchmarks_Track.html

**Why:** GSM1K and benchmark-contamination/generalization considerations.

---

## 22. Final recommendation

**Proceed with SafeAdapt-Math, but treat the verifier as the main technical contribution rather than merely an optional add-on.**

The most defensible version of the project has three connected parts:

**Diagnose:** Measure whether and how accessibility-oriented rewrites alter mathematical meaning or instructional demand.

**Detect:** Build and evaluate a conservative verifier that identifies potentially unsafe rewrites.

**Mitigate:** Test whether one constrained revision improves safety, and compare the resulting cost and quality with deterministic formatting.

The project should be presented as **neurodiversity-informed educational-content safety research**, not as a validated tutoring intervention for neurodivergent learners.

The question we ultimately want to answer is:

**When AI rewrites a math problem to make it easier to access, can we trust that the student is still being asked to solve the same problem—and what checks are needed before a teacher should use that rewrite?**

That is concrete, experimentally testable, socially motivated, and achievable without student records or recruitment.

---

## 23. What must be completed before claiming experimental findings

This document specifies the study; it does not report a completed experiment.

Before presenting actual model comparisons or failure rates, we must:

1. Select and freeze the exact two model versions.
2. Collect verbatim outputs using versioned prompts.
3. Save source problem IDs and generation metadata.
4. Apply the human annotation rubric.
5. Distinguish observed failures from constructed examples.
6. Evaluate the verifier on held-out annotations.
7. Report uncertainty, false negatives, and unsuccessful revisions.
8. Make the benchmark and evaluation procedure reproducible, subject to dataset and provider terms.

**The strongest immediate improvement for the professor is to bring four real, logged model outputs: one faithful rewrite, one mathematical error if observed, one instructional-leakage case if observed, and one case where the model correctly leaves a clear problem unchanged.**

If those failures do not occur in the initial sample, report that fact and use the constructed stress tests to explain what the verifier is designed to guard against. Do not invent failures.

**End of dossier.**
