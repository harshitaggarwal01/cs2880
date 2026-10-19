# Our Project, Explained Simply

*Talking notes for the discussion with the teaching staff. Everything here is plain language. The examples are real model outputs unless they are marked "made-up".*

---

## 1. The project in one sentence

> **Teachers are starting to use AI to make math word problems easier to read for students who struggle with reading or attention. We check whether the AI keeps it the *same* problem, or quietly changes it or solves part of it. Then we build an automatic checker that catches the bad versions before a student sees them.**

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

## 4. What we actually do (three steps)

| Step | What we do | Question it answers |
|---|---|---|
| **1. Measure** | Take 124 real math problems. Have two AI models (OpenAI and Google) rewrite each one: in "plain language", in "chunks", and with the realistic teacher prompt above. We also make a *non-AI* version that just splits the original sentences onto separate lines. We hand-label every output. | How often does AI rewriting change the math or give away the solution? Does how the teacher asks matter? |
| **2. Detect** | Build an automatic **checker** that compares the original and the rewrite and says **PASS / REVIEW / REJECT**. | Can a computer catch the unsafe rewrites before a student sees them? |
| **3. Fix (or don't)** | Rejected rewrites get **one** repair attempt, then are checked again. We compare everything against the simple non-AI version. | Is repairing worth it? When is no AI at all the better choice? |

**Where the AI is** (two places):
- the rewriting models we audit;
- one layer of our checker, an AI "critic" from a *different* company than the rewriters, so they don't share the same blind spots.

The rest of the checker is plain code: it compares numbers, looks for words like "subtract" or "Step 1", and checks that the same question is asked.

---

## 5. What the checker does, concretely (real outputs)

| Rewrite | What our checker says |
|---|---|
| The cookie problem with "Steps to try: Find 30% of 200. Subtract it…" | **REJECT**: new operation words ("find", "subtract"); new step-by-step structure ("Steps to try", numbered steps) |
| Building problem, *"The remaining floors are each 3 feet taller"* rewritten with headings **"Stories 1 to 10" / "Stories 11 to 20"** | **REJECT**: a new number (11) that the student was supposed to work out (20 − 10 remaining floors) |
| A clean chunked version: one fact per line, same numbers, same question | **PASS** |
| A faithful rewrite that repeats "add" ("add 50 rows of beads") | **REVIEW** (a false alarm). This is why the checker has an AI layer and a human-review option, not just word matching |

**A made-up example** (not from a model) of the scarier kind of error, which simple number-checking misses:
> Original: "Omar has **three times as many** stickers as Lena. Lena has 8." → answer 24
> Bad rewrite: "Omar has **three more** stickers than Lena. Lena has 8." → answer 11

Same numbers, different math. Catching this needs the smarter layers (the AI critic, and having both versions turned into an equation and compared).

---

## 6. The final output of the project

At the end of the semester we hand over four things:

1. **A labelled benchmark.** 124 math problems, about 700 AI rewrites, each hand-labelled: same math? gives anything away? actually easier to read? Anyone can use it to test their own tool.
2. **The checker (open-source code).** A tool that takes *original + rewrite* and returns PASS / REVIEW / REJECT with the reason. We report honestly:
   - how many unsafe rewrites it catches (target: at least 90%);
   - how many safe ones it wrongly flags (the extra review work it creates);
   - what it costs per problem.
3. **A clear recommendation** for teachers and the companies building these tools. For example:
   - "Use a constrained prompt, not a casual one."
   - "Strip anything after the problem itself."
   - "For short problems, just split the sentences; no AI needed."
   - "Always human-check X, never Y."
4. **A small demo.** Paste a problem, see the AI rewrite and the checker's verdict side by side.

---

## 7. How it helps, and the social impact

**Who benefits:**
- **Students who need adapted materials** get versions that are easier to *read* but still the *same problem*. They keep the same chance to learn and to show what they know as their classmates.
- **Teachers** get a safety net. Instead of re-checking every rewrite, they look only at the ones flagged REVIEW or REJECT.
- **Ed-tech companies** (the tools teachers already use) can put the checker in front of their AI as a guardrail, and use our benchmark to test themselves.

**Our impact chain**, which mirrors the course's "data-to-deployment" idea:

```text
Dense math text is a barrier  →  teachers use AI to adapt it  →  AI sometimes changes or solves the task
        →  OUR CHECKER catches it  →  students get safe, fair adapted problems
```

**What we are honest about:**
- We do **not** claim this improves learning, or that it helps students with ADHD or dyslexia specifically. Proving that would need a study with students, which is a natural next step.
- We do **not** detect or label anyone's diagnosis. Adaptations are options anyone can choose.
- If our results say "the simple non-AI version is just as good" or "humans still need to check everything", **that is a valid and useful answer.** Using less AI can be the socially responsible outcome.

---

## 8. What we already found (small pilot, 10 problems, 70 real outputs)

| How the AI was asked | Result |
|---|---|
| Our careful prompt ("keep every number, don't hint, don't solve") | **50 of 50** kept the math correct and gave nothing away. Some were not actually easier to read: sentence fragments, almost no change. |
| The casual teacher prompt | **13 of 20** were unsafe. One model added solution steps every time; the other used step labels or gave away an in-between number. |
| Our simple checker on these 70 | Caught **all 13** unsafe ones. Wrongly rejected 1 safe one, and sent about 1 in 4 safe ones to human review. |

**What this tells us:** the biggest risk isn't the AI "getting the math wrong". It is the AI **being too helpful**, in the way teachers actually use it. These are pilot numbers on 10 problems with preliminary labels, not results. The main study checks them at scale with the real models.

---

## 9. Questions the professor might ask, with short answers

**"Isn't this just evaluating LLMs? Where's the social impact?"**
The impact is in deployment. These tools are already in classrooms and are used for the students who most need fair treatment. We are building and testing the safety gate that should sit between the AI and the student, and we measure whether it's good enough to trust.

**"Why not just tell teachers to write better prompts?"**
That's one of our conditions. If careful prompts fix most of it, that's a finding we'll recommend. But teachers use whatever tool they have, many tools don't expose the prompt, and our pilot shows that the default casual request goes wrong most of the time.

**"What if the AI almost never makes mistakes?"**
Then we report that, with confidence intervals. That is useful: it tells schools what's safe. Even then, the realistic-prompt results and the checker still matter.

**"Hasn't someone done this?"**
Pieces of it:
- Carnegie Learning used GPT-4 to rewrite math problems for weaker readers (Norberg et al. 2025). They found keeping the problem structure intact was hard, but they didn't systematically measure "giving away the solution".
- A 2026 paper (DFT-GEN) checks dyslexia-friendly text for "answer leakage", but not for math specifically.

What we add:
- a math-specific check (numbers, relationships, the question asked) *and* graded "how much did it give away";
- realistic versus careful prompts;
- a checker tested against human labels;
- a comparison with no AI at all.

**"Why this dataset (GSM8K)?"**
It is real school-level math with known answers, free to use, and standard in research. We add two other datasets to check that results aren't specific to it.

**"How do you know your labels are right?"**
Both of us label independently on a 30% overlap, we measure agreement, and we follow a written rubric. We also hide which model wrote each rewrite while labelling.

**"Where does neurodiversity come in?"**
It is the motivation. Many neurodivergent students benefit from clearer language and chunked information, and that is exactly the support being automated. We keep it *diagnosis-free*: the goal is that any adapted version is a fair version, whoever chooses it.

---

## 10. The 30-second version (say this first)

> "Teachers are using AI to rewrite math problems in simpler language for students with reading or attention difficulties. We found that when you ask the AI the way a teacher normally would, it often adds solution steps or gives away part of the answer. In our pilot, one model did it 10 out of 10 times. Those students end up with an easier, different problem than their classmates, and nobody notices. Our project measures how often this happens across two major AI models, builds an automatic checker that flags unsafe rewrites before they reach a student, and tests whether fixing them, or skipping AI entirely, works better. The output is a labelled benchmark, an open-source checker, and clear guidance for teachers and tool builders."
