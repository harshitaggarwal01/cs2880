# Source Audit of the Earlier Documents

**Scope.** Every factual claim and citation in the ChatGPT deep-research report (`deep-research-report_3.md`) and the "SafeAdapt-Math" writing-block dossier, checked on 2026-10-16.

**Method.**
- Search results from primary pages: publisher, ACL Anthology, arXiv, ERIC/PMC, official repositories and data cards.
- Direct reads of GitHub and Hugging Face.
- Direct download of GSM8K and ASDiv, so their counts and licenses were checked against the files themselves.

**Access limitation.** Springer, arXiv and ACL full texts could not be fetched from this environment, so verdicts on paper *details* rest on abstracts and indexed snippets.

| # | Claim in earlier documents | Verdict | Corrected / supported wording |
|---|---|---|---|
| 1 | Norberg et al. used GPT-4 to rewrite MATHia content for emerging readers (IJAIED) | ✅ Confirmed | IJAIED 35(2):587–626, 2025 (online 2024), doi 10.1007/s40593-024-00420-2 |
| 2 | Norberg et al. produced "~200 rewritten problems from 30 scenarios across two MATHia workspaces" | ❌ Unverifiable → **removed** | Not found in any accessible source. MATHia problems are generated from "scenarios", but these numbers were not confirmed. |
| 3 | Norberg et al.: other LLMs were tried; only GPT-4 retained correct problem structure | ✅ Confirmed (indexed snippet of article text) | "At the time only GPT-4 was able to retain the correct structure of the problem in revision" |
| 4 | Norberg et al.: mixed learner outcomes | ✅ Confirmed | Mastery more likely with GPT-4 rewrites, "but this benefit was not consistent across all content areas"; error rates higher in some areas |
| 5 | Almoubayyed et al. 2023: 12,374-learner randomized field trial of human rewrites | ✅ Confirmed, venue corrected | Short **poster/late-breaking** paper, AIED 2023, CCIS 1831, pp. 200–205. Emerging readers were *predicted* by a model. Effect sizes (~13% higher mastery, ~30% less time) come from a later EDM paper by the same group: cite them as secondary. |
| 6 | Agrawal & Carpuat 2024: best supervised system leaves ≥14% of questions unanswerable | ✅ Confirmed | TACL 12:432–448; nine systems evaluated |
| 7 | InfoLossQA: 1,000 QA pairs, 104 simplifications, medical abstracts; automated methods struggle | ✅ Confirmed | ACL 2024, pp. 4263–4294 |
| 8 | EDUMATH, ACL 2026, >11,000 generated problems, teacher annotations, student study | ✅ Confirmed | aclanthology 2026.acl-long.1973; first posted as arXiv 2510.06965 |
| 9 | GSM-Symbolic shows sensitivity to names, numbers and clauses; strongest claims later scrutinized | ✅ Confirmed | ICLR 2025. Critique: arXiv 2605.28700 (authors not verified) re-analyzes with mixed-effects models |
| 10 | GSM-Plus | ✅ Confirmed | ACL 2024, pp. 2961–2984 |
| 11 | GSM1K "public full release is now available" | ⚠️ Partly | Public on Hugging Face `ScaleAI/gsm1k` (1,205 rows, created 2025-03-31). **No license declared:** do not redistribute text. |
| 12 | ASDiv: 2,305 English MWPs | ✅ Confirmed (file counted) | ACL 2020; CC BY-NC 4.0 (repo README) |
| 13 | GSM8K: 7,473 train / 1,319 test; MIT; repo archived April 2026 | ✅ Confirmed (files counted; license read) | Archived 2026-04-08 |
| 14 | Model "GPT-6 Luna (`gpt-6-luna`)" | ✅ Exists | In the openai-python SDK model list; released 2026-09-22; $0.10/$0.50 per 1M tokens (snippet). No dated snapshot found. |
| 15 | Model "Gemini 3.8 Flash (`gemini-3.8-flash`)", `thinking_level="low"` | ✅ Exists | GA; thinking levels low/medium/high (minimal errors); temperature removed or ignored on 3.8; $0.75/$3.75 introductory until 2026-12-31 |
| 16 | OpenAI docs warn output is nondeterministic | ✅ Plausible / general | Temperature is only accepted with `reasoning.effort="none"`; we log returned model IDs |
| 17 | Diffit adapts math word problems to reading levels | ✅ Vendor claim | Diffit literacy page. Feature claim only, not evidence of efficacy or fidelity. |
| 18 | Khan Academy: AI content can contain errors; review it | ✅ Confirmed | Khanmigo help-center article |
| 19 | CAST UDL 3.0; W3C cognitive accessibility guidance; 1EdTech AccessForAll / PNP | ✅ Confirmed | UDL 3.0 released July 2024. W3C COGA "Making Content Usable" is a Working Group Note (2021), supplemental to WCAG. PNP v3.0 is in draft / candidate final: don't call it final. |
| 20 | WCAG 2.2 = ISO/IEC 40500:2025 | ✅ Confirmed | W3C announcement 2025-10-21 |
| 21 | Perrault, Fang, Sinha & Tambe, data-to-deployment pipeline | ✅ Confirmed | AI Magazine 41(4):3–16 (2020) |
| 22 | Daroczy et al. 2015; Walkington et al. 2018 | ✅ Confirmed | Frontiers in Psychology 6:348; AERJ 55(2):362–414 |
| 23 | (Earlier chat) Fuchs et al., 325 second graders | ✅ Confirmed | Scientific Studies of Reading 22(2):152–166 (2018) |
| 24 | (Earlier chat) MathSpring RCT: 53 teachers, 2,003 students, no improvement | ✅ Confirmed | Feng et al. 2025, J. Computer Assisted Learning 41(5), e70106 |
| 25 | (Earlier chat) Westwood et al. computerized cognitive training meta-analysis | ⚠️ Venue wrong | **Molecular Psychiatry** 28:1402–1414 (2023), not JAMA Psychiatry. Not needed for this project. |
| 26 | Harvard COMPSCI 2880, Fall 2026, Tambe | ✅ Confirmed (listing snippet) | Previously CS 288; course site cs288.hsites.harvard.edu |
| 27 | Sample size: 124 (report) vs 135 (dossier) vs "125 → 625 outputs" | ⚠️ Internal inconsistency | **Resolved and frozen:** 10 dev + 100 main + 12 GSM1K + 12 ASDiv (see `data/frozen/MANIFEST.json`) |
| 28 | Double annotation: 30% (report) vs "about half" (dossier) | ⚠️ Inconsistent | 30% stratified, with a κ/AC1 ≥ 0.7 threshold and re-annotation if missed |
| 29 | ZIP/sandbox download links and SHA-256 checksums in the report | ❌ Dead | Sandbox links never persisted. This package replaces them; checksums in `CHECKSUMS.sha256`. |
| 30 | "Captured empirical outputs could not be produced" | ✅ Honest at the time | This package now contains 70 real outputs with provenance (`pilot/`) |

## Prior art missing from both earlier documents
- **DFT-GEN (2026):** high novelty threat. Fidelity gates for task drift and answer leakage in dyslexia-friendly chunking.
- **Patel et al. (2023, JCAL):** GPT-3 readability simplification of math assessment items.
- **Ikram et al. (2026):** validate-then-repair for personalized math problems.
- **Suchdev & Lovato (2026, AIES):** audit of LLM cultural adaptation of GSM8K problems.
- **Zhao, Knežević & Käser (2026, ACL):** two-stage answer-leakage detector.
- **Measurement theory:** Abedi & Lord 2001; Sireci, Scarpati & Li 2005; Kieffer et al. 2009; Sato et al. 2010; Elliott et al. 2010; AERA/APA/NCME Standards 2014.
- **Judge reliability:** Panickssery et al. 2024; Kim et al. 2025.

## Claims to avoid
- "LLMs frequently corrupt math problems." Not shown for current models; our constrained pilot saw no corruption.
- "Chunking helps ADHD students" or "plain language helps dyslexic students". No controlled evidence for math.
- "The verifier guarantees equivalence."
- Any rate from the pilot, which has n = 10 and preliminary labels.
