# External-tool collection protocol (Phase 3A)

## Purpose

The main study audits two API models. Teachers use products: tools built on top of models, with their own prompts,
templates and post-processing. This protocol collects a small, paired sample of what those tools return for the same
frozen source problems, so the same verifier and labelling pipeline can estimate how often each tool's rewrite is
unsafe (changes the maths, or does the student's thinking). It is an audit of outputs, not a product review.

## Tool shortlist (candidates pending ToS review)

Diffit, MagicSchool, Khanmigo teacher tools, and the consumer ChatGPT and Gemini interfaces. This is a candidate
list only. The final list is whatever survives the terms-of-service check below; a tool is dropped, not worked around,
if its terms do not allow the capture.

## Terms-of-service checklist (before any capture)

For each tool, read the current terms and acceptable-use policy, save the date and URL in `tos_notes`, and answer:

1. Is automated access prohibited? (We capture by hand, but note it.)
2. Are there research, benchmarking or competitive-evaluation restrictions?
3. Are users allowed to keep and store outputs? Is redistribution of outputs restricted?
4. Does the account type we have (free, educator, trial) fall under different terms?

Record the result in `tos_checked` (YES = read and capture is permitted; NO = not yet read or not permitted) and
`tos_notes`. If any answer prohibits our use, drop the tool. `import_external.py` refuses rows that are not YES.

## Manual capture, step by step

1. Use the frozen source problems (`data/frozen/main.jsonl`, the same ids used for the API models). The capture list
   is a fixed subset agreed in advance (for example the first 40 `main` problems), not chosen after seeing outputs.
2. Open a fresh session or chat for each problem so earlier replies cannot influence it.
3. Use the realistic prompt text verbatim from `prompts/naive_v1.txt` (the USER section, with the problem pasted in
   place of `{problem_text}`). For tools with fixed controls (for example a "simplify" button), use the default
   setting and write the control path in `ui_path`; `prompt_used` then records what was typed or selected.
4. One capture per source per tool. Do not regenerate because a reply looks bad or good.
5. Copy the whole reply, unedited, into `raw_response`. Put the part a teacher would give to a student in
   `adapted_problem`, or leave it blank to score the full reply.
6. Record `tool`, `tool_version_or_date` (version string if shown, otherwise the capture date), `ui_path`,
   `captured_by` and `captured_at`.
7. Start from `data/external/TEMPLATE.csv`; keep the file under `data/external/` (git-ignored).

## Quality control

A second person spot-checks 10% of rows (random, at least 5 per tool): same source, same prompt, recorded reply
matches what the tool shows (re-run if the UI keeps history). Disagreements about transcription are fixed in the CSV
and noted in `notes`; the tool's reply is never re-sampled to get a different answer.

## Data handling

Captured outputs stay on the capturing machine. They are not committed, not shared in the release, and not pasted
into the paper beyond short quotes. Results are reported in aggregate only. No vendor is named in public results
without this protocol attached, so readers can see how the capture was done. Only frozen public problems are ever
entered into a tool; no student data is involved.

## Labelling

Import with `python src/import_external.py data/external/captures.csv --run-id external-v1`, then run
`verify.py` on the resulting `generations.jsonl`. Humans label about 30 items per tool (blinded sheets from
`make_annotation_sheets.py`, the same rubric as the main study); `ppi.py` combines those labels with the verifier's
predictions on the remaining items to give a per-tool unsafe rate with a confidence interval.

## What is reported

- Per-tool unsafe rate with a PPI confidence interval.
- Distribution of leakage types (answer, intermediate value, operation, steps, relevance) and fidelity failures.
- Illustrative excerpts limited to short quotes, with no reproduction of full replies.
- The protocol itself (this document) and the ToS decisions, as an appendix.

## Limitations

- UI versions, models behind the tools and default prompts change without notice; results describe the capture date.
- A single capture per item: no estimate of within-tool run-to-run variance.
- Small, fixed problem set and a few tools; rates are descriptive, not a ranking of products.
- Manual capture and manual segmentation of the student-facing text add transcription error, which the 10% spot
  check bounds but does not remove.
- Teachers may use these tools differently (extra context, follow-up edits) than a single-shot capture.
