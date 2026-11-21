# SafeAdapt-Math — project video (Nov 23): 15 slides, ~16 min, narrated by Cathy and Harshit

**Instructor's brief:**
- Same content as Nov 16: motivation, problem statement, approach, evaluation.
- A clear problem statement, with the main finding right after it.
- Few charts: two here; everything else is in `TECHNICAL_APPENDIX.md`.
- One slide on ethics and broader impact (slide 13).
- 15–17 minutes.

**Speakers:**

| Speaker | Slides | Approx. words |
|---|---|---|
| **Cathy** | 1–5, 11, 13 | ~1,050 |
| **Harshit** | 6–10, 12, 14, 15 | ~1,250 |

**Number rules:**
- Every number states its n.
- "Checker" numbers are automated decisions on the 1,044-rewrite main run.
- Human numbers are the adjudicated labels on 70 calibration rewrites of 10 practice problems.
- The 54 answer changes were flagged by recomputation and verified by hand (2026-11-20).
- Main-study human labels arrive Dec 1. No AI-stand-in numbers are quoted.

---

## 1 · Title [0:25] — CATHY, then HARSHIT
**SafeAdapt-Math: When "easier to read" becomes "easier to solve"**
Auditing AI accessibility rewrites of math word problems
Harshit Aggarwal · Cathy Liu · CS 2880 AI for Social Impact · Brown University · Nov 2026

> **CATHY:** Hi, I'm Cathy…
> **HARSHIT:** …and I'm Harshit.
> **CATHY:** Our project looks at something teachers already do all the time: asking an AI to rewrite a math problem so a student with a disability can read it more easily. We found that the rewrite often changes the task without anyone noticing, and that it takes more than a second AI to catch it.

---

## 2 · Motivation [1:20] — CATHY
**Teachers already use AI to adapt tests. Nobody checks what it changes.**
- Students with IEPs and 504 plans are legally owed **accommodations**: the same task, made accessible (plain language, chunking).
- A **modification** makes the task easier. It is a different legal and educational category, and it changes what the grade means.
- Teachers are increasingly encouraged to use AI for this. No tool tells them when a rewrite crossed the line.
- The failure is invisible: a rewrite that hands over the steps looks *more* helpful.
- The harm lands on the students the accommodation was meant to protect.

> **CATHY:** Roughly one in seven US public-school students gets special-education services under an IEP, and more have 504 plans. For these students the law draws a pretty careful line.
> An *accommodation* keeps the task the same and changes how it's presented, like shorter sentences or one fact per line. A *modification* changes the task itself, and with it what the grade actually certifies.
> Now teachers are being told to use AI to make accommodations. Honestly, that's reasonable: rewriting a dense word problem is exactly what these models are good at. The problem is that nobody checks the output.
> And the failure that worries us isn't an obvious wrong answer, which a teacher would spot. It's a rewrite that quietly does some of the thinking: it names the operation, or works out an intermediate number. That version *looks* more supportive, so it's exactly the one a busy teacher is most likely to approve.
> Here's what that means in practice. Say a student's IEP grants plain-language math tests. If every rewritten problem names the operation to use, the score now measures something easier than the standard, and nobody can tell from the grade: not the teacher, not the parents, not the student.

---

## 3 · Problem statement [1:05] — CATHY
**Given a math word problem and an AI rewrite of it, decide automatically, at low cost, and with a statistical guarantee, whether the rewrite is the same task: an accommodation, not a modification.**
- **Same task (fidelity):** every quantity, relation, condition and the question are preserved, so the answer is unchanged.
- **Nothing given away (no leakage):** no added steps, operations, relevance hints or derived values.
- We measure three things:
  1. **How often** rewrites change the task, with careful prompts and with the prompt teachers actually type.
  2. **How well** checkers catch it: rules, answer recomputation, and AI judges from free to frontier.
  3. **Whether** a school that can't pay for frontier models can get the same protection.

> **CATHY:** So here's our problem in one sentence. Given a problem and its AI rewrite, can we decide, automatically, cheaply, and with an error rate we can actually state, whether the rewrite is still the same task?
> "Same task" really means two things. First, fidelity: every number, relation and condition survives, and the question is the same, so the answer doesn't change. Second, no leakage: the rewrite can't do any of the reasoning for the student.
> Why does it need to be automatic? A teacher might adapt twenty or thirty problems for one worksheet, and a district tool might do thousands. Nobody's going to re-solve all of those by hand. And "usually right" isn't good enough for a legal accommodation. A district needs to be able to say how often a rewrite it approved changes the task.
> We ask three questions: how often does this go wrong, can a checker catch it, and can a school with no budget get the same protection as one that can pay for frontier models?

---

## 4 · Main finding, up front [1:10] — CATHY
**The prompt teachers type turns most rewrites into modifications, and AI judges don't reliably catch the subtle ones.**
1. **The prompt decides it.**
   - Careful prompts: the checker rejects 13% (82/620), and adjudicated human labels find 8% unsafe (4/50).
   - The realistic teacher prompt: the checker rejects 99% (297/300), and humans find 70% unsafe (14/20).
2. **AI judges miss most real errors.** Of 54 careful-prompt rewrites whose answer verifiably changed:
   - the best paid judge flags 18;
   - the best free large judge flags 7.
3. **AI is a lenient grader.** On every disputed case, AI took the lenient reading, and every one of those cases turned out to be unsafe (5 of 5).

> **CATHY:** Before we get into how we did this, here's what we found.
> First, the risk is in the prompt, not the model. With carefully written instructions, our checker rejects about one rewrite in eight. With the short prompt a teacher would actually type, "make this easier for a student with ADHD or dyslexia", it rejects 297 out of 300. Our human labels show exactly the same split.
> Second, you can't just fix this by asking another AI. On rewrites where the answer verifiably changed, the best paid judge we tried caught only a third, and the best free one about one in eight.
> And third, and this one surprised us: on the hard cases, AI went with the lenient reading every single time, and it was wrong every single time. Harshit will walk through it.

---

## 5 · What a "helpful" rewrite does [0:50] — CATHY
**One example (practice problem, free 3B rewriter, plain-language prompt)**
- **Original:** "James builds a 20 story building. The first 10 stories are each 12 feet tall each. **The remaining floors are each 3 feet taller.** How tall is the building?"
- **Rewrite:** "…**The remaining 10 stories are 15 feet tall each.**"
- It reads more clearly, and it has done two steps for the student: 20 − 10 = 10 floors, and 12 + 3 = 15 feet.
- Verdicts:
  - Qwen 32B judge: SAFE.
  - Gemma 12B judge: SAFE.
  - Claude Haiku and GPT-6 Luna: UNSAFE.
  - Our free rule layer: **REJECT** (two derived values).

> **CATHY:** Here's what that looks like on a real practice problem. The original says the remaining floors are each 3 feet taller. The rewrite says the remaining 10 stories are 15 feet tall each.
> Is it easier to read? Sure. But it has also done two calculations the student was supposed to do: how many floors are left, and how tall each one is.
> Two free AI judges called this safe; two paid ones didn't. A very simple rule, "is there a number here that wasn't in the original?", caught it right away. We see that pattern again and again. Harshit?

---

## 6 · Approach: measure → check → decide [0:55] — HARSHIT
**Measure the failure, build a layered checker, then turn its verdicts into decisions with statistical guarantees.**
- **Measure:**
  - real problems;
  - AI rewrites under careful and realistic prompts;
  - a non-AI control;
  - blind, double human labels as ground truth.
- **Check:** free rules → AI critic → recompute the answer as a program → PASS / REVIEW / REJECT.
- **Decide:**
  - a guaranteed-safe PASS threshold;
  - the cheapest order of checks;
  - label-efficient failure rates;
  - where a district should audit.
- **Prespecified:** the design and checker were frozen before any study data was generated, and tuned on 10 separate practice problems only.

*Visual: three boxes, Measure → Check → Decide (as Nov 16).*

> **HARSHIT:** Thanks, Cathy. Our approach has three parts. First, measure the failure honestly: a fixed design and blind human labels. Second, build a checker that layers cheap rules, an AI critic, and recomputing the answer. Third, turn that checker into an actual decision procedure with statistical guarantees, because a verdict on its own isn't a policy.
> Why layers? Because each kind of check fails differently. Rules are cheap and exact, but they only see what you wrote them for. AI critics understand meaning, but a fluent rewrite can talk them into "looks fine". Recomputation is objective, but only works when both versions can be turned into a little program. The design is about combining them, and knowing how each one breaks.
> Everything was prespecified: we froze the design and the checker before generating a single study rewrite, and tuned only on ten separate practice problems.

---

## 7 · Study design and the checker [1:20] — HARSHIT
**1,044 AI rewrites of 124 problems, all checked on one university GPU, at $0**
- **Problems:** 124 from GSM8K test, ASDiv and GSM1K, stratified by solution steps × relational cues.
- **Conditions:**
  - careful plain-language and chunked prompts;
  - the realistic teacher prompt;
  - a non-AI sentence splitter as the control.
- **Rewriters:** three free open-weight models (Qwen 14B, Gemma 12B, Llama 3B).
- **Checker, three layers:**
  - **Rules:** quantities, relations, quantifiers, leaked operations and derived values. Free and deterministic.
  - **AI critic:** a rubric verdict with cited evidence.
  - **Program check:** extract both versions as programs and recompute. A different answer means REJECT.
- **Judges compared:** 3 free local models and 4 paid frontier models (Claude Haiku and Sonnet 5.5, GPT-6 Luna and GPT-6.1 Sol). Paid spend: $11.42, including a pilot.
- **Labels:** 1,062 items, two blind annotators, 30% double-labelled (due Dec 1).

> **HARSHIT:** Here are the details. We took 124 problems from three datasets, stratified by how many steps they need and how many relational phrases they contain. Three free models rewrote each one, with careful prompts and with the realistic prompt. That gave us 1,044 rewrites. As a control, a little script with no AI just splits sentences.
> The checker has three layers. The rules catch new numbers, lost relations and leaked operations. The AI critic gives a rubric verdict and has to quote its evidence. And the program layer turns both versions into small programs, recomputes the answer, and rejects the rewrite if the answers differ. We also ran seven different judges, three free and four paid, on the same rewrites. The paid ones cost us about eleven dollars in total.
> For ground truth there's a fixed labelling plan. Every realistic-prompt rewrite gets labelled. Half the careful-prompt problems are labelled, paired across models so comparisons are fair. And thirty percent are labelled by both of us. That's 1,062 items, about seventeen hours each, which we're working through now.

---

## 8 · Result 1: the prompt decides it [1:30] — HARSHIT
**Same models, same problems: careful prompts keep the task; the prompt teachers type breaks it.**

![](fig_prompt.png)

- The control (sentence splitter, no AI) gets **0 REJECT** of 124, so the rules don't fire on a faithful rewrite.
- What the realistic prompt adds, of 300 rewrites:
  - the operation to use (266);
  - precomputed values (260);
  - equations (239);
  - numbered solution steps (201).
- It is not memorization: GSM1K, held-out problems models haven't trained on, rejects at 16% (10/61), matching GSM8K's 13%.

> **HARSHIT:** OK, first result. Blue is the checker on the full main run. Orange is our adjudicated human labels.
> With careful prompts, the checker rejects 13%, and humans find 8% unsafe. With the realistic prompt it flips completely: the checker rejects 99%, and humans find 70% unsafe. Same models, same problems. The only thing that changed is the prompt.
> When you look at what the realistic prompt adds, it's basically scaffolding. The operation to use shows up in 266 of 300 rewrites, precomputed values in 260, numbered steps in 201. And the control, the script that only splits sentences, gets zero rejections. So the checker isn't just punishing any change.
> And this isn't memorization: on GSM1K, fresh problems models haven't trained on, the rejection rate is the same.
> The takeaway: the harder the model tries to help, the more it modifies. So a safeguard can't depend on teachers writing perfect prompts. It has to check what comes out.

---

## 9 · Result 2: AI judges miss most real errors [1:30] — HARSHIT
**Of 54 careful-prompt rewrites whose answer verifiably changed, no AI judge catches even half.**

![](fig_judges.png)

- Paid judges flag 2–3× more than the large free ones, but the best still misses 36 of 54.
- Price buys little: Sonnet costs about 15× Haiku for 3 more catches.
- Llama 3B "catches" 45 only by flagging 85% of everything. That is not a judge.
- Judges disagree: Qwen 32B and Gemma 12B agree on only 4 of the rewrites they flag.

> **HARSHIT:** Second result. We took the 54 careful-prompt rewrites where the answer actually changed: our recomputation flagged them, and we verified every one by hand. These are real errors. Then we asked: how many does each AI judge catch?
> The best one, GPT-6.1 Sol, catches 18. Two-thirds slip through. Claude Sonnet flags 16, at roughly fifteen times Haiku's cost for three more catches. The free large models catch 7 and 4. And the small Llama model looks great until you notice it flags 85 percent of everything, which would just bury a teacher in false alarms.
> What are the judges missing? Mostly quiet changes. Across the careful-prompt rewrites, our rules see a relation or quantifier added in 53 and lost in 45: a comparison reworded, a condition dropped. The rewrite still reads smoothly, so a model asked "is this the same problem?" tends to say yes. Recomputation doesn't care how smooth it reads.
> So for us, an AI verdict is a useful signal, but not a decision. It's one layer, and human labels stay the ground truth.

---

## 10 · Result 3: the line is a value judgement, and AI leans lenient [1:20] — HARSHIT
**Calibration: two blind annotators, 70 rewrites of 10 practice problems**
- **Human agreement on SAFE:** κ 0.79, 93% raw. All 5 SAFE disagreements run one way: annotator A strict, B lenient.
  - The disputed cases are subtle: an "If he ate half…" condition restated as a fact, a dangling "If…" fragment, and "Here is what you need to know".
- **An AI adjudicator sided with the lenient label on all 5, and all 5 are unsafe on review.**
- **An AI labeller (Mistral 24B) lands on the lenient side too.**
- The strict reading is now written into the rubric (v1.2), with examples, before main-study labelling.

> **HARSHIT:** The third result surprised us. Before labelling the study, Cathy and I each labelled 70 practice rewrites, independently. We agree pretty well on what's safe: kappa 0.79. But every disagreement went the same direction: one of us stricter, one more lenient.
> And the cases are subtle. Say the problem asks, "If he ate half the cookies, how many are left?", and the rewrite says, "He ate half the cookies." Is that the same task? No. It drops a condition. That's exactly the kind of case we split on.
> Then we handed exactly these hard cases to AI. An AI adjudicator sided with the lenient reading five out of five times, and on review all five were unsafe. An AI labeller we tested landed on the lenient side too.
> It's the same pattern as the judges: AI reads a helpful-looking rewrite charitably. So the rubric now spells out the strict reading, with examples, and the final labels come from people.

---

## 11 · Result 4: what "free" buys a school [1:00] — CATHY
**The whole pipeline runs at $0 on hardware a district or university already has, but only above a size threshold.**
- **Free tier:** one GPU, about 21.5 hours for the whole study. Student materials never leave campus.
- **Small models break the output contract:**
  - Llama 3B produced a usable chunked rewrite for **1 of 124** problems, against 124/124 for Qwen 14B and Gemma 12B.
  - As a judge it flags 85% of everything.
- **Teacher time is the binding cost.** At about 1.5 minutes per REVIEW, with a third of careful-prompt rewrites going to REVIEW, that is about 10 extra minutes per 20-problem worksheet. That is what the decision layer shrinks.

> **CATHY:** Fourth: what does this mean for schools without much money? Everything we built runs for free on a single GPU. The whole study took about twenty-one and a half hours. So a district doesn't need a frontier-model contract, and student work never has to leave campus.
> But there's a floor. The smallest model we tried, 3 billion parameters, couldn't follow the chunking format: one usable rewrite out of 124. And as a judge it flags almost everything.
> The real cost turns out to be teacher time. Every flagged rewrite takes a teacher about a minute and a half, and with a third of rewrites going to review, a 20-problem worksheet costs about ten extra minutes. That's exactly what the last piece of the system is built to cut.

---

## 12 · From checker to decision [1:05] — HARSHIT
**A checker is not a policy. These turn it into one (built, unit-tested and run end to end; final numbers on human labels Dec 3).**
- **Guaranteed PASS:** conformal risk control and Learn-then-Test certify that the unsafe rate among passed rewrites stays below a chosen α, with high probability.
- **Failure rates with a fraction of the labels:** prediction-powered inference, stratum-weighted, combines a labelled subset with checker verdicts on everything, unbiased.
- **Cost-aware cascade:** the cheapest ordering of rules → AI critic → human for a target safety level, reported as a Pareto frontier.
- **Where to audit:** a Stackelberg audit game that spends a district's limited audit budget where a lenient tool would do most harm.
- **Holds under attack:**
  - An adaptive red-team attacker barely moved held-out recall (11/15 → 10/15 over 3 rounds).
  - Weighted conformal keeps its guarantee under distribution shift.

> **HARSHIT:** A checker gives you verdicts, but a school needs decisions it can stand behind. So we built a decision layer on top.
> Conformal risk control works a bit like setting a passing bar on a practice exam. We use labelled rewrites to pick how confident the checker has to be before we pass something, so that among everything we pass, the unsafe rate stays below a target, say five percent, with a statistical guarantee.
> Prediction-powered inference gives unbiased failure rates from a fraction of the human labels. The cascade finds the cheapest order of checks for a given safety level. And the audit game, straight from this course, tells a district where to spend a limited audit budget.
> All of this is built and tested, and runs end to end. The real numbers come once the human labels are in, on December 3rd. And it holds up: we built an attacker that learns to sneak leaks past the checker, and over three rounds it barely moved our recall.

---

## 13 · Ethical implications and broader impact [1:40] — CATHY
**Who could be helped, who could be harmed, and what we did about it**
- **Intended benefit:** fair access for students with disabilities. Teachers can use AI accommodations without silently lowering the bar, and districts can audit vendor tools.
- **Risks:**
  - **False reassurance.** A PASS is evidence, not proof. An over-trusted checker can turn modifications into IEP-compliant paperwork. Mitigations: a statistical guarantee, REVIEW routes to a person, and humans have final authority.
  - **Whose line?** "Accommodation vs modification" is a value judgement. Our rubric reflects two annotators, who are also the authors, not special-education teachers, students or families. It must be validated with them before any deployment.
  - **Over-blocking.** A strict checker can deny students a genuinely helpful rewrite. A false REJECT also hurts them, so we report false alarms alongside misses.
  - **Equity and privacy.** Cheaper models fail more often, so under-resourced schools carry more risk. Our free, on-campus tier keeps student materials local.
  - **Dual use.** The red-team attacker shows how to evade a checker. It is released as an evaluation tool.
- **Transparency:** AI assistance (Claude) was used for code, analysis drafts and a first-pass adjudication that the owner overruled.
- **Scope:** English, GSM-style arithmetic, one rubric, no student outcomes yet.

> **CATHY:** We want to take a minute on the broader picture. The benefit we're after is simple: students with disabilities get the access they're owed without the task quietly getting easier, and districts get a way to audit the tools they buy.
> But there are real risks. The biggest one is false reassurance. A checker that says "PASS" can turn a modification into paperwork that looks compliant. That's why we attach a statistical guarantee, send uncertain cases to a person, and keep humans as the final authority.
> Second, where you draw the line is a value judgement. Our rubric reflects the two of us, and we're also the authors. It isn't special-education teachers, or students, or families. It needs their input before anyone deploys something like this.
> Third, being strict has a cost too. Blocking a rewrite that would actually have helped also hurts the student, so we report false alarms, not just catches.
> Fourth, equity: cheaper models fail more often, so poorer schools carry more of the risk. Our free, on-campus setup is meant to close that gap and keep student data local.
> And a couple of honesty notes. The red-team attacker is dual-use, so we frame it strictly as an evaluation tool. We used AI assistance, Claude, for code and analysis drafts. And our scope is narrow: English, arithmetic word problems, and no student outcomes yet.

---

## 14 · Limitations and what's next [0:45] — HARSHIT
- **Main-study human labels:** 1,062 items, two blind annotators, due **Dec 1**; joint adjudication Dec 2–3.
- Then on human labels: final failure rates, the guaranteed PASS threshold, the cascade frontier and the audit game. The final report follows.
- **Limitations:**
  - human labels so far cover 70 practice items;
  - recomputation can't check about 8% of rewrites;
  - three rewriters only;
  - prompts in English.
- **Next:**
  - validate the rubric with special-education teachers;
  - test with students, to see whether "safe" rewrites actually help;
  - extend beyond arithmetic word problems.

> **HARSHIT:** Where we are: generation and checking are done. The main-study human labels are due December 1st, and after that every decision-layer result gets its real numbers.
> The main limitations right now: our human labels only cover 70 practice items, the recomputation can't check about 8 percent of rewrites, and it's three models on English arithmetic problems. Next, we'd love to get special-education teachers to validate the rubric, and to run a student study to see whether the "safe" rewrites actually help.

---

## 15 · Take-home [0:40] — HARSHIT
- **The failure is real and common:** with the prompt teachers type, 297 of 300 rewrites gave away operations, values or steps.
- **AI can't grade AI here:** the best judge caught 18 of 54 verified errors, and AI took the lenient side on every hard case.
- **What works:** rules plus answer recomputation, an AI critic as one signal, humans as ground truth, and statistical guarantees on what gets passed. It runs at $0 on a school's own hardware.
- **Same problem, easier to read, verified before it reaches a student.**

> **HARSHIT:** So, to wrap up. AI accessibility rewrites change the task a lot more often than they seem to, especially with the prompts teachers actually use. Another AI isn't a reliable referee: it misses most real errors, and it's lenient exactly where it matters. What works is layered: cheap rules and recomputation, AI as one signal, people as ground truth, and guarantees on what we pass. And all of it runs for free.
> **CATHY:** Same problem, easier to read, and checked before it reaches a student.
> **HARSHIT:** Thanks for watching.

---

### Recording checklist
- Use 1080p. The slide text must be readable on a laptop screen: no table smaller than about 20 pt (the main tables are in the appendix).
- Total length 15:30–16:30. Rehearse slides 9, 12 and 13; they're the densest.
- Rotate the OpenRouter key (it is in a session transcript).
- Submit by **Nov 23, end of day**. Send `TECHNICAL_APPENDIX.md` (or its PDF) with the video.
