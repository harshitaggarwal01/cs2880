# SafeAdapt-Math: Preserving the Math While Simplifying the Words

**CS 2880 · AI for Social Impact · two-person team · one-page brief (2026-10-16)**

**Problem.** Teachers use generative AI to make math word problems easier to read: plainer language, information in chunks. Tools such as Diffit market exactly this. In math, a fluent rewrite can silently change *the task itself*: a dropped condition, a reversed comparison, or, keeping every number, an added plan that does the reasoning for the student. Students who rely on adapted materials should not get a corrupted or easier problem because their version came from an AI.

**What we already observed (real pilot, 10 GSM8K problems, 70 outputs, preliminary labels).** We tested a realistic teacher prompt: *"Rewrite this math word problem so it is easier to understand for a student with ADHD or dyslexia. Use simple language and break it into small chunks."*
- With this prompt, one frontier model appended a step-by-step solution plan to **10 of 10** problems ("Find 30% of 200. Subtract it from 200…").
- A second model leaked solution structure or an intermediate count in **3 of 10** ("Stories 11 to 20").
- With our **constrained** prompts, all 50 outputs kept the mathematics intact. The failures were presentation problems (sentence fragments, near-copies).
- Verbatim examples: `docs/professor_examples.md`.

**Research questions.**
1. **Fidelity under constrained prompts.** How often do two current LLMs change the mathematics or leak solution information? What kinds of failure occur?
2. **Realistic prompts.** How much worse are adaptations made from the prompts teachers actually use?
3. **Verification.** Can a hybrid verifier catch unsafe adaptations with high recall? Its layers are deterministic number/cue checks, an extraction-and-program check, and a critic from a different model family.
4. **Repair.** Does one constrained repair pass raise the safe-and-useful yield?
5. **AI versus no AI.** When is deterministic formatting good enough that no AI is needed?

**Method.**
- **Sources.** 124 frozen problems: 100 from the GSM8K test split, plus 12 GSM1K and 12 ASDiv problems as an external check. A separate 10-problem dev set is used only for development.
- **Generators.** `gpt-6-luna` and `gemini-3.8-flash`, each producing a plain-language version and a chunked version under constrained prompts. On the 100 main problems they also respond to the realistic teacher prompt.
- **Baseline.** A deterministic chunker that cannot change meaning.
- **Annotation.** Blinded human labels for math fidelity, leakage level (0 none → 3 value revealed), ambiguity, and presentation quality. 30% of items are double-annotated, with agreement reported as κ and Gwet's AC1.
- **Verifier and repair.** The critic is `claude-sonnet-5-5`, a different model family from both generators. We report verifier recall on human-labelled unsafe items, layer ablations, review burden and cost. Flagged items get one repair and are re-annotated.
- **Statistics.** Source-clustered bootstrap CIs and exact McNemar tests on paired comparisons.
- **Cost.** About $13 in API calls and about 16 hours of annotation per person.

**Why it is new.**
- Prior work rewrote math problems for readability and measured outcomes (Norberg et al. 2025, GPT-4 in MATHia, where structure preservation was a known obstacle) or generated new problems (EDUMATH 2026).
- The closest work is DFT-GEN (2026), which gates dyslexia-friendly texts on task drift and answer leakage but is not math-specific.
- We separate **mathematical-fidelity loss** from **graded instructional leakage**. Both are *modifications* rather than *accommodations* in testing terms (Abedi & Lord 2001; Sireci et al. 2005).
- We test realistic versus constrained prompting, evaluate a verifier and a repair pass against human labels, and compare against a deterministic baseline.

**Social impact and scope.** Neurodiversity-informed and diagnosis-free. The goal is a safety gate in a real workflow (teacher → AI tool → student), not a claim about learning gains. We do not claim that the adaptations help students with ADHD or dyslexia; that would need a learner study, which we name as future work. "Use deterministic formatting" or "keep humans reviewing everything" are acceptable conclusions.

**Deliverables.**
- An open benchmark: frozen sources, logged outputs, adjudicated labels.
- An annotation rubric and failure taxonomy.
- A verifier and repair code, with tests.
- A failure gallery.
- A small demo and the final report.

**Key readings:** Norberg et al. 2025 (IJAIED) · DFT-GEN 2026 · Agrawal & Carpuat 2024 (TACL) · InfoLossQA 2024 · Sireci, Scarpati & Li 2005 · Perrault, Fang, Sinha & Tambe 2020.
