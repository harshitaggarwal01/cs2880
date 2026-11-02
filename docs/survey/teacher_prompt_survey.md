# Teacher prompt survey (instrument, Phase 3B)

**Status: prepared only. Do not distribute or collect responses until the Harvard CUHS determination is in hand.**
This semester the instrument and the loader (`src/realistic_prompts.py`) are built and tested on made-up data.

## Purpose

Our "realistic prompt" condition uses one guessed teacher request (`prompts/naive_v1.txt`). This survey asks
teachers how they actually phrase requests to simplify a math problem, so we can add real wording variants to the
audit and see whether the results depend on the phrasing.

## Who

Classroom teachers, special-education staff and tutors who have used an AI tool for math materials. Adults only
(18+). We ask for no student information.

## Consent text (shown first)

> You are invited to a short survey (about 5 minutes) from a Brown University course project on how AI tools rewrite
> math word problems for students who need accessibility support. Participation is voluntary and anonymous. You may
> skip any question or stop at any time. Please do not include student names, student work or any information that
> could identify a student, a school or yourself in your answers. We use responses to build a set of example prompt
> wordings and to report aggregate counts (for example, which tools are used). Example wordings may be quoted after
> removal of identifying details. Responses are stored locally on the researchers' computers and deleted at the end of
> the project (target: May 2027) unless you ask us earlier through the optional contact at the end. Clicking
> "Continue" means you agree to take part.

## Questions

1. What is your role? (classroom teacher / special-education teacher or aide / tutor / other: ____)
2. Which grade bands do you work with? (select all: K-2, 3-5, 6-8, 9-12)
3. Which AI tools have you used to prepare math problems or other materials? (select all; ChatGPT, Gemini, Claude,
   Copilot, Diffit, MagicSchool, Khanmigo, other: ____, none)
4. How often do you ask an AI tool to simplify or rewrite a math problem? (never / a few times a year / monthly /
   weekly / daily)
5. **Paste the exact text you typed last time you asked an AI to simplify a math problem.** Do not include student
   names or data. Replace the problem itself with "[problem]" if you prefer. (prompt_1)
6. **Paste the exact text of another request you have used for this, if any.** (prompt_2, optional)
7. Before you give an AI-rewritten math problem to a student, what do you check? (free text)
8. What would make you trust an AI rewrite enough to use it without reading it closely? (free text)
9. Have you ever found an AI rewrite that changed the maths or gave away part of the solution? If so, what happened?
   (free text; no student details)
10. Optional: if we may contact you with a follow-up question, enter an email address. It is stored separately from
    your answers and never shared.

## Data handling

- Responses are exported as a CSV and stored locally under `data/survey/` (git-ignored); not committed, not uploaded
  to public repositories.
- The contact email from Q10 is stored in a separate file and removed from the response CSV before analysis.
- Prompts (Q5, Q6) are de-identified before use: emails and links are stripped automatically
  (`realistic_prompts.load_survey`), and we read every prompt for names or school details before it is written to
  `prompts/`. Prompt files contain no names and no respondent identifiers.
- Reported results: prompt variants and aggregate counts only.

## Human-subjects note

A survey of adults about their professional practice, with anonymous responses and no sensitive topics, is likely
exempt under 45 CFR 46.104(d)(2) (exempt category 2). Harvard's Committee on the Use of Human Subjects (CUHS) must
make that determination **before any collection**. The determination, the date and the reference number are recorded
here when received: ______. Until then no one outside the research team sees this instrument, and no responses exist.
