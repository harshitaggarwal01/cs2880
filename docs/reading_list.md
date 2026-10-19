# Reading List (prioritized)

Entries marked † were verified at abstract or search-snippet level only. The full texts could not be fetched from this environment, so check details yourself.

## Tier 1: everyone reads these before rubric freeze (about 5 hours)

| # | Reading | Why it matters to us | Focus on |
|---|---|---|---|
| 1 | **Norberg et al. (2025)**. Rewriting content with GPT-4 to support emerging readers in adaptive mathematics software. *IJAIED* 35(2):587–626. https://doi.org/10.1007/s40593-024-00420-2 | The closest prior work on math rewriting. Only GPT-4 kept problem structure; outcomes were mixed across content areas. Defines what we cannot claim as new. | Their prompt and style guide; how they handled structure errors; the content areas where error rates rose |
| 2 | **DFT-GEN (Yu et al., 2026)**. Beyond simplification: fidelity-preserving visual accessibility in dyslexia-friendly educational texts. arXiv:2608.13583 † | The closest novelty threat: chunking with fidelity gates for task drift and answer leakage. | How they define and detect leakage and task drift; whether any math items are included; their human pilot |
| 3 | **Agrawal & Carpuat (2024)**. Do text simplification systems preserve meaning? *TACL* 12. https://aclanthology.org/2024.tacl-1.24 | Fluent is not faithful: even the best system left 14% or more of comprehension questions unanswerable. Methodological basis for not trusting readability metrics. | The reading-comprehension evaluation design |
| 4 | **Sireci, Scarpati & Li (2005)**. Test accommodations for students with disabilities: the interaction hypothesis. *RER* 75(4). Plus **Abedi & Lord (2001)**, The language factor in mathematics tests. *AME* 14(3). | Theory: accommodation vs modification. Abedi & Lord's linguistic-modification types are our "allowed edits". | The differential-boost idea; the list of modification types |
| 5 | **Perrault, Fang, Sinha & Tambe (2020)**. AI for social impact: learning and planning in the data-to-deployment pipeline. *AI Magazine* 41(4). | Course framing: what deployment decision our results inform. | The deployment and evaluation sections |

## Tier 2: owner of each component reads these

| Component | Reading | Why |
|---|---|---|
| Fidelity rubric | **Trienes et al. (2024)**, InfoLossQA, *ACL*. https://aclanthology.org/2024.acl-long.234 | LLM simplifications lose information often, and LLM detectors miss it: argues for human labels as ground truth |
| Fidelity rubric | **Patel et al. (2023)**, Improving mathematics assessment readability: do LLMs help? *JCAL* 39(3). † | Earlier LLM simplification of math items ("noisy and often unrelated to the input") |
| Leakage rubric | **Zhao, Knežević & Käser (2026)**, Answer leakage robustness of LLM tutors, *ACL*. † | Two-stage detector (rules, then LLM judge): template for our verifier |
| Leakage rubric | **Macina et al. (2023)**, MathDial, *Findings of EMNLP* · **Maurya et al. (2025)**, MRBench, *NAACL* † | "Telling" versus scaffolding in tutoring |
| Verifier | **Panickssery, Bowman & Feng (2024)**, LLM evaluators favor their own generations, *NeurIPS* · **Kim et al. (2025)**, Correlated errors in LLMs, *ICML* † | Why the critic comes from a third model family |
| Verifier | **Ikram et al. (2026)**, Multi-agent validation and refinement of personalized math problems. arXiv:2604.05160 † | The same validate-then-repair shape: cite and compare |
| Data | **Cobbe et al. (2021)**, GSM8K · **Zhang et al. (2024)**, GSM1K, *NeurIPS D&B* · **Miao et al. (2020)**, ASDiv, *ACL* | What the datasets are; contamination |
| Robustness | **Shi et al. (2023)**, GSM-IC, *ICML* · **Mirzadeh et al. (2025)**, GSM-Symbolic, *ICLR* (and its 2026 critique, arXiv:2605.28700 †) · **Li et al. (2024)**, GSM-Plus, *ACL* | Small wording changes alter difficulty; solver agreement is not an equivalence oracle |
| Generation precedent | **Christ et al. (2026)**, EDUMATH, *ACL* | Teacher plus LLM-judge evaluation at scale; generation, not preservation |
| Audit template | **Suchdev & Lovato (2026)**, Auditing LLM cultural translation of math word problems, *AIES* † | An audit paper on GSM8K adaptations: structure to borrow |

## Tier 3: motivation and accessibility framing (skim)
- **Fuchs et al. (2018)**, *Scientific Studies of Reading* 22(2). 325 second graders: text comprehension predicts word-problem solving.
- **Walkington, Clinton & Shivraj (2018)**, *AERJ* 55(2). Readability effects differ by student background.
- **Daroczy et al. (2015)**, *Frontiers in Psychology* 6:348. Review of linguistic and numerical difficulty factors.
- **Almoubayyed et al. (2023)**, AIED poster (CCIS 1831). 12,374-learner field trial of human rewrites.
- **CAST UDL Guidelines 3.0 (2024)** · **W3C COGA, Making content usable (2021)** · **1EdTech AccessForAll / PNP**. Accessibility design practice and diagnosis-free preferences. These are not efficacy evidence.
- **Kieffer et al. (2009)**, *RER* 79(3) · **Sato et al. (2010)**, NCEE 2009-4079 · **Elliott et al. (2010)**, *Exceptional Children* 76(4) †. The empirical accommodation literature.

## Do not cite for efficacy
Vendor pages (Diffit, MagicSchool, Khanmigo, Immersive Reader) show that products and workflows exist, nothing more. There is no controlled evidence that chunked text improves math performance for ADHD learners, and "dyslexia fonts" have null results. Do not imply either.
