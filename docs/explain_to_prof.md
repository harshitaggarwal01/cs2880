# Our Project, Explained Simply

*Talking notes for the discussion with the teaching staff. Everything here is plain language. The examples are real model outputs unless they are marked "made-up".*

---

## 1. The project in one sentence

> **Teachers are starting to use AI to make math word problems easier to read for students who struggle with reading or attention. We measure whether the AI keeps it the *same* problem, or quietly changes it or solves part of it. We build a checker with a stated safety guarantee that catches the bad versions before a student sees them. And we learn a simple policy for when to use AI at all.**

---

## 2. The problem, with one real example

A teacher has a student who finds long word problems hard to read (because of dyslexia, ADHD, still learning English, or just dense text). The teacher pastes the problem into an AI tool and asks for an easier version. Tools like Diffit and MagicSchool are built for exactly this.

**The original problem (from GSM8K, a standard dataset of school math problems):**
> Out of the 200 cookies that Javier baked from the recipe he learned online, his wife took 30%, and his daughter took 40 from the remaining cookies. If he ate half of the remaining cookies, how many cookies did they not eat?

**What a teacher might type:**
> "Rewrite this math word problem so it is easier to understand for a student with ADHD or dyslexia. Use simple language and break it into small chunks."

**What the AI actually returned (Claude Opus, real output, shortened):**
> 1. Javier baked **200** cookies.
> 2. His wife took **30%** of the cookies.
> 3. Then his daughter took **40** of the cookies that were left.
> 4. Then Javier ate **half** of the cookies that were left.
>
> **Question:** How many cookies were **not** eaten?
>
> **Steps to try:**
> 1. Find 30% of 200. Subtract it from 200.
> 2. Subtract the 40 cookies his daughter took.
> 3. Find half of what is left. …

**What went wrong.** The top part is a nice, easier-to-read version. Then the AI added **"Steps to try"**, which tell the student exactly what to calculate and in what order. The answer is still the same, but the **task is not**:

- Classmates have to *figure out* what to do. That is the actual math skill being taught and tested.
- The student with the "accessible" version only has to *follow instructions*.

So the student who needed help reading got an **easier, different problem**. Nobody noticed, because it looks helpful.

**This was not a one-off.** With that ordinary teacher prompt, this model added a solution plan to **10 out of 10** problems we tried.

---

## 3. Why this matters (the "why")

1. **Accessibility should change how a problem looks, not what it asks.** Testing research has a name for this:
   - An **accommodation** changes the presentation only (bigger font, read-aloud, simpler sentences). It is fair.
   - A **modification** changes what is being measured. It is not the same test.

   AI rewriting can turn an accommodation into a modification without anyone realizing.
2. **The students affected are the ones who rely on adapted materials.** If their version is silently easier, two things happen:
   - They lose the chance to practice the real skill.
   - Teachers get a false picture of what they can do: "they can solve it" when really the AI did the reasoning.

   Over time that widens gaps instead of closing them.
3. **The opposite failure is also possible.** The AI can drop a fact or flip a relationship, so the student is asked something *wrong*. A student who "fails" a broken problem gets blamed for the AI's mistake.
4. **Teachers can't check everything.** These tools are attractive because they save time. Carefully checking every rewritten problem takes away exactly that time. Even Khan Academy tells teachers to review AI-generated content. *What does "review it" actually mean for a math problem, and can a computer do most of it?* That is our question.
5. **The language barrier is real.** Research shows reading and language ability strongly affect performance on math word problems (Fuchs et al. 2018: 325 second graders). Simplifying language is worth doing. It just has to be done safely.

---

## 4. What we actually do (four steps)

| Step | What we do | Question it answers |
|---|---|---|
| **1. Measure** | Take 124 real math problems. Have two AI models (OpenAI and Google) rewrite each one: in "plain language", in "chunks", and with the realistic teacher prompt above. Also make a *non-AI* version that just splits the original sentences onto separate lines. Label the outputs by hand, using *prediction-powered inference* to get accurate failure rates from fewer human labels (§5C). | How often does AI rewriting change the math or give away the solution? Does how the teacher asks matter? |
| **2. Detect** | Build an automatic **checker** that compares original and rewrite and says **PASS / REVIEW / REJECT**. Calibrate it with *conformal risk control* so a PASS comes with a stated guarantee (§5A). Run it as a *cost-aware cascade*: free checks first, paid checks only when needed (§5B). | Can a computer catch unsafe rewrites before a student sees them, at a cost a school can afford? |
| **3. Fix** | Rejected rewrites get **one** repair attempt and are then checked again. | Is repairing worth it, or is it better to block? |
| **4. Decide** | Learn a simple **policy** (a *contextual bandit*) that picks, problem by problem, the best way to produce the accessible version, including "no AI, just split the sentences" (§5D). | When should AI be used at all, and which setup works best for which kind of problem? |

---

## 5. The four methods, in plain words

These four pieces are what make this more than "a good prompt plus a second AI to check it". Each one turns a vague promise into a number someone can rely on.

### A. A checker that comes with a guarantee (conformal risk control)

**The problem:** a checker that says "PASS" is only useful if you know how often PASS is wrong.

**What we do:** we use our hand-labelled examples to set the checker's threshold with a statistical method called **conformal risk control**. Afterwards we can make a statement like:

> "Of the rewrites this checker PASSes, **at most 5% are unsafe**, guaranteed with high probability, provided new problems look like the ones we calibrated on."

**Analogy:** a smoke detector tuned so it almost never misses a real fire. The price is more false alarms. Here, a false alarm means more items sent to a teacher for review.

**What we report:** a simple curve of *safety guarantee* vs. *share of rewrites sent to a human*. Example (illustrative numbers, not results): "at a 5% guarantee, teachers review about 30% of rewrites; at 10%, about 15%." A school can pick its point on that curve.

### B. Check cheaply first, expensively only when unsure (cost-aware cascade)

**The problem:** the AI critic costs money and time, and teacher time costs the most.

**What we do:** run the checks in order and stop as soon as we are confident:

```text
1. Free rule-based check   (instant, $0)        → clear REJECT or clear PASS? stop here
2. AI critic               (~1 cent per problem) → confident? stop here
3. Teacher review          (minutes of a human)  → only what is still uncertain
```

We choose where to stop by minimizing **unsafe items that slip through + cost + teacher minutes**.

**Real pilot hint:** the free check alone already rejected all 13 unsafe rewrites in our pilot. The expensive layers matter mainly for subtle cases, like "three times as many" turned into "three more".

**What we report:** cost and teacher minutes per 100 problems, alongside how many unsafe rewrites get through.

### C. Accurate failure rates from fewer human labels (prediction-powered inference)

**The problem:** hand-labelling every AI output is slow, and we want to test more than two models, ideally the actual tools teachers use.

**What we do:** humans label a random subset, and the AI critic labels everything. **Prediction-powered inference** (Angelopoulos et al., 2023) combines the two. The answer stays **unbiased**, because human labels correct the critic's mistakes, and the error bars are **smaller** than with human labels alone.

**What it enables:** statements like "Tool X added solution steps to 62% ± 6% of problems" (illustrative) without hand-labelling hundreds of extra outputs. That makes auditing real classroom tools affordable (optional extension).

### D. A policy for which method to use (contextual bandit)

**The problem:** there is no single best way to make a problem accessible. A short problem may need no AI at all; a long, tangled one may benefit from a careful AI rewrite.

**What we do:** treat it as choosing between options ("arms"):
- (a) split the sentences, no AI;
- (b) model A with the careful prompt;
- (c) model B with the careful prompt;
- (d) a model plus one repair.

For each problem we look at simple features (length, number of steps, whether it has percentages or comparisons). The **reward** is "safe *and* actually easier to read", minus cost. A **contextual bandit** (Thompson sampling) learns which option to pick for which kind of problem.

**What we report:** a readable policy. For example (illustrative):
- "Problems under 40 words → just split the sentences."
- "Multi-clause problems with comparisons → model B with the careful prompt, plus the checker."

The policy is compared against "always use AI" and "never use AI".

**Honest caveat:** we learn this offline from our labelled data, a simulation of deployment, not from live classroom use.

---

## 6. What the checker does, concretely (real outputs)

| Rewrite | What our checker says |
|---|---|
| The cookie problem with "Steps to try: Find 30% of 200. Subtract it…" | **REJECT**: new operation words ("find", "subtract"); new step-by-step structure ("Steps to try", numbered steps) |
| Building problem, *"The remaining floors are each 3 feet taller"* rewritten with headings **"Stories 1 to 10" / "Stories 11 to 20"** | **REJECT**: a new number (11) that the student was supposed to work out (20 − 10 remaining floors) |
| A clean chunked version: one fact per line, same numbers, same question | **PASS** |
| A faithful rewrite that repeats "add" ("add 50 rows of beads") | **REVIEW** (a false alarm). This is why the checker has an AI layer and a calibrated threshold, not just word matching |

**A made-up example** (not from a model) of the scarier kind of error, which simple number-checking misses:
> Original: "Omar has **three times as many** stickers as Lena. Lena has 8." → answer 24
> Bad rewrite: "Omar has **three more** stickers than Lena. Lena has 8." → answer 11

Same numbers, different math. Catching this needs the smarter layers: the AI critic, and having both versions turned into an equation and compared.

---

## 7. The final output of the project

1. **A labelled benchmark.** 124 math problems, about 700 AI rewrites, each labelled: same math? gives anything away? actually easier to read? Anyone can use it to test their own tool.
2. **A calibrated checker (open-source code).** It takes *original + rewrite* and returns PASS / REVIEW / REJECT with the reason. It comes with:
   - a **stated guarantee** ("at most X% of PASSed items are unsafe");
   - a measured false-alarm rate;
   - a cost per problem.
3. **A decision policy.** A simple, readable rule for when to use AI, which setup to use, and when to just split sentences, compared against "always AI" and "never AI".
4. **Clear recommendations** for teachers and tool builders. For example:
   - "Use a constrained prompt, not a casual one."
   - "Strip anything after the problem itself."
   - "Run the free check on everything, and the paid check only on uncertain cases."
5. **A small demo.** Paste a problem and see the rewrite, the checker's verdict and reason, and what the policy would have chosen.

---

## 8. How it helps, and the social impact

**Who benefits:**
- **Students who need adapted materials** get versions that are easier to *read* but still the *same problem*. They keep the same chance to learn and to show what they know as their classmates.
- **Teachers** get a safety net. Instead of re-checking every rewrite, they look only at what the checker flags, and they know how reliable a PASS is.
- **Ed-tech companies** (the tools teachers already use) can put the checker in front of their AI as a guardrail, and use the benchmark to test themselves.

**Our impact chain**, which mirrors the course's "data-to-deployment" idea:

```text
Dense math text is a barrier  →  teachers use AI to adapt it  →  AI sometimes changes or solves the task
   →  OUR CHECKER (with a guarantee) catches it, OUR POLICY decides when AI is even needed
   →  students get safe, fair adapted problems at a cost schools can afford
```

**What we are honest about:**
- We do **not** claim this improves learning, or that it helps students with ADHD or dyslexia specifically. Proving that would need a study with students, which is a natural next step.
- We do **not** detect or label anyone's diagnosis. Adaptations are options anyone can choose.
- If the results say "the simple non-AI version is just as good" or "humans still need to check everything", **that is a valid and useful answer.** Using less AI can be the socially responsible outcome, and the bandit policy is designed to find exactly that.

---

## 9. Who it is for and how it fits in

### Who it is for

| Who | Where they meet the problem today | How our work helps them |
|---|---|---|
| **Students who use adapted materials** (struggling readers, students with dyslexia or ADHD, English learners, anyone who prefers shorter text) | They get a "simplified" worksheet or app screen and have no way to know it was changed | Versions that are easier to read **and** still fair: same question, same thinking required |
| **Teachers and special-education staff** | They paste problems into an AI tool and must decide whether to trust the result | They only check what is flagged, the flag says *why*, and they know how reliable a PASS is |
| **Ed-tech companies** (Diffit-, MagicSchool-type tools; tutors like MATHia) | Their AI produces the rewrites, and they carry the risk if those rewrites are wrong | A ready-made guardrail, a benchmark to test against, and a policy for when to call the AI at all |
| **Curriculum publishers and test makers** | They need many accessible versions of the same items, and accommodations must not change what is measured | Batch-check whole problem banks and get a report of which adapted items are safe |
| **Researchers** | No public benchmark exists for "did the rewrite keep the same math task?" | Labelled data, rubric and code are reusable |

### How it fits into an existing tool

The checker only needs two pieces of text: **the original problem and the rewrite**. It returns a verdict and a reason:

```text
Teacher clicks "Make it easier" in their usual tool
        │
        ▼
Policy picks the method for this problem (e.g. "short problem → just split sentences, no AI")
        │
        ▼
(If AI was used) checker compares original vs. rewrite  ──►  PASS    → shown as normal
                                                         ──►  REVIEW  → shown with a note:
                                                         │              "check this: 'remaining' was dropped"
                                                         ──►  REJECT  → repaired once and re-checked,
                                                                        or fall back to the no-AI version
```

**What a tool would get back, illustratively:**

```text
verdict: REJECT
reasons: - adds solution steps ("Steps to try", numbered steps)
         - adds operation words not in the original ("find", "subtract")
safe alternative: the original sentences split one per line (no rewording)
```

**Why it's easy to adopt:**
- The first check is free and instant.
- The AI layer costs about a cent per problem and runs only when needed.
- It needs **no student data and no diagnoses**, only the problem text.
- It can run live inside an app, in bulk over a worksheet or question bank, or as a test a company runs before releasing its AI.

### How it helps, in one line each
- **Student:** "My version is easier to read, but it's still my work."
- **Teacher:** "I only double-check the few the system warns me about, and I know how much to trust the rest."
- **Tool builder:** "We can show our 'simplify' button doesn't change the math or give away answers, with numbers."
- **School or test maker:** "Our accommodations stay accommodations, not easier tests."

---

## 10. Where it can go later (future ideas, not part of this semester)

*Everything in this section is a possible next step. None of it is built or promised in this project.*

### Research next steps
1. **Test with real students.** Do safe adapted versions help struggling readers more than other students (a "differential boost")? That would show the adaptation is a fair accommodation. Needs ethics approval (IRB) and a school partner.
2. **Audit the real tools teachers use.** Run the same problems through popular classroom AI tools. PPI (§5C) makes this affordable.
3. **Other subjects.** Science word problems and reading-comprehension questions have the same risk.
4. **Other languages.** Many tools translate and simplify at the same time, for English learners.
5. **Other kinds of adaptation.** Read-aloud scripts, diagrams, and practice versions where hints *are* intended (with a "how much help is allowed" setting).
6. **Smaller, cheaper checker.** Train a small open model on our labels so schools can run it for free, even offline.
7. **Run the bandit live.** Let the policy learn from real teacher feedback ("this version was helpful / not") instead of offline labels.

### Things that could be built from it (product ideas)

| Idea | What it would be | Who would use it |
|---|---|---|
| **"Safe Simplify" add-on** | Google Docs / Classroom add-on: select a problem, get a checked easier version, with warnings shown inline | Teachers |
| **Checker API** | A web service ed-tech companies call before showing any AI-rewritten problem, returning a verdict and a guarantee level | Ed-tech companies |
| **Question-bank auditor** | Upload a worksheet or test bank; get a report of which adapted items are safe, which need review, and why | Publishers, districts, test makers |
| **Public benchmark and leaderboard** | Rank AI tools on "keeps the same problem" vs. "gives the answer away" | Schools choosing tools; researchers |
| **Back into an adaptive tutor** | Our original idea (AccessPath): a math tutor where each student picks how problems are shown, and the checker guarantees every version is still the same problem | Students directly |

**Why this matters for the future:** AI-adapted learning materials are going to become normal. A shared, open standard for "is this still the same problem?", backed by measured guarantees, is a public good that makes the whole category safer. That is a bigger impact than any single app.

---

## 11. What we already found (small pilot, 10 problems, 70 real outputs)

| How the AI was asked | Result |
|---|---|
| Our careful prompt ("keep every number, don't hint, don't solve") | **50 of 50** kept the math correct and gave nothing away. Some were not actually easier to read: sentence fragments, almost no change. |
| The casual teacher prompt | **13 of 20** were unsafe. One model added solution steps every time; the other used step labels or gave away an in-between number. |
| Our free rule-based check on these 70 | Caught **all 13** unsafe ones. Wrongly rejected 1 safe one, and sent about 1 in 4 safe ones to human review (too many: the calibration and cascade in §5 are meant to fix this). |

**What this tells us:** the biggest risk isn't the AI "getting the math wrong". It is the AI **being too helpful**, in the way teachers actually use it. These are pilot numbers on 10 problems with preliminary labels, not results. The main study checks them at scale with the real models.

---

## 12. Questions the professor might ask, with short answers

**"Isn't this just evaluating LLMs? Where's the social impact?"**
The impact is in deployment. These tools are already in classrooms and are used for the students who most need fair treatment. We build and test the safety gate that should sit between the AI and the student, and a policy for when AI should be used at all.

**"Where's the AI / decision-making beyond prompting?"**
Four places:
- a checker calibrated with **conformal risk control**, so PASS carries a guarantee;
- a **cost-aware cascade** that decides when to spend money or teacher time;
- **prediction-powered inference** for reliable audit numbers from few labels;
- a **contextual bandit** that learns when to use which method, including no AI.

**"Isn't this just a better system prompt?"**
A prompt is a *claim* ("don't give hints"). We produce *evidence*: how often each model breaks the rule under real prompts, a test set to check any fix against, and a checker with a measured guarantee. If a better prompt fixes most of it, that's a finding we'll recommend, and we'll have the numbers to prove it.

**"What if the AI almost never makes mistakes?"**
Then we report that with confidence intervals. That is useful: it tells schools what's safe. The realistic-prompt results, the guarantee and the policy still matter.

**"Hasn't someone done this?"**
Pieces of it:
- Carnegie Learning used GPT-4 to rewrite math problems for weaker readers (Norberg et al. 2025). Keeping the problem structure intact was hard, but they didn't systematically measure "giving away the solution".
- A 2026 paper (DFT-GEN) checks dyslexia-friendly text for "answer leakage", but not for math specifically.

What we add:
- a math-specific check *and* graded "how much did it give away";
- realistic versus careful prompts;
- a checker with a guarantee;
- a policy compared against no AI.

**"Why this dataset (GSM8K)?"**
It is real school-level math with known answers, free to use, and standard in research. We add two other datasets to check that results aren't specific to it.

**"How do you know your labels are right?"**
Both of us label independently on a 30% overlap, we measure agreement, and we follow a written rubric. We also hide which model wrote each rewrite while labelling.

**"Where does neurodiversity come in?"**
It is the motivation. Many neurodivergent students benefit from clearer language and chunked information, and that is exactly the support being automated. We keep it *diagnosis-free*: the goal is that any adapted version is a fair version, whoever chooses it.

---

## 13. The 30-second version (say this first)

> "Teachers are using AI to rewrite math problems in simpler language for students with reading or attention difficulties. We found that when you ask the AI the way a teacher normally would, it often adds solution steps or gives away part of the answer. In our pilot, one model did it 10 out of 10 times. Those students end up with an easier, different problem than their classmates, and nobody notices. We measure how often this happens across two major AI models. We build a checker that flags unsafe rewrites and comes with a stated safety guarantee. And we learn a simple policy for when AI should be used at all, including when just splitting the sentences is better. The output is a labelled benchmark, an open-source checker, a decision policy, and clear guidance for teachers and tool builders."

---

## Notes: other method ideas we considered (not in the plan)

*Kept for discussion. These are possible stretch goals or future work, not commitments.*

- **Red-team game (attacker vs. checker).** An "attacker" AI tries to rewrite problems so they leak hints *subtly* while still passing the checker. We would harden the checker over a few rounds. A good robustness test and a possible stretch goal (about 2–3 days). Limitation: real AI tools aren't trying to fool the checker, so this tests worst-case robustness, not typical behaviour.
- **Audit game (Stackelberg inspection game).** A school district or platform can only manually audit a fraction of AI outputs, and tool vendors choose how careful to be. Game theory would find the audit plan that minimizes unsafe content reaching students. This is in the style of Tambe-lab security and audit games. Limitation: vendors don't currently respond strategically to audits, so it would be a simulation or policy section. Better as future work.
- **Restless bandits (as in the ARMMAN maternal-health work).** These fit repeated decisions about *people* over time, such as which student gets a teacher check-in this week. They don't fit this project, which makes decisions about problems, not students. They would fit if we return to the adaptive-tutor idea (AccessPath).
- **Mechanism design / incentives.** There is no real strategic behaviour by teachers or students to model here, so it would feel forced. Not pursued.
