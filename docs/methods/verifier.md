# Verifier: versions and tuning log

The verifier is three layers (`src/deterministic_checks.py`, `src/verify.py`):
1. Rules (deterministic, free): numbers lost or added, derived-value leaks, operation and step cues, relational phrases, units, question wording, length, chunk format.
2. AI critic (`prompts/critic_v1.txt`).
3. Program recompute: extract both texts as a program (`prompts/extract_v1.txt`) and compare the values.

The decision policy (REJECT / REVIEW / PASS) is in the `verify.py` docstring. Every verify row stores `verifier_version`; rows without it are v1.0.

**PASS means "no problems detected under these checks", not "proven equivalent".**

## v1.1 (2026-11-11), tuned on the 10 dev problems only

No study problem (`main`, `ext_*`) was opened. The prompts and the critic are unchanged; only the rules and the decision policy changed.

| Change | Before (v1.0) | After (v1.1) | Why (dev evidence) |
|---|---|---|---|
| `program:RELATIONS_DIFFER` | REVIEW when the extracted relation types differ, even if the answers MATCH | not a review reason when the answers MATCH; `program.relation_types_equal` is still stored as a logged feature for cascade/conformal/distill | Fired on 18/40 pilot rewrites; all 40 answers matched. The extractor labels the same relation differently across paraphrases. |
| New value written only as a cardinal word one…ten | `LEAK_DERIVED_VALUE` or `QTY_ADD` REJECT | REVIEW flag `NUMBER_WORD_ADDED` | "taken out in **three** ways" (counting the deductions) was REJECTed because 3 is derivable from the source. Digits keep the strict rule ("Stories 11 to 20" still REJECTs); words above ten, and "twice"/"half"/"dozen", keep the old rule. |
| Synonym classes | each phrase counted on its own | a swap inside {altogether, in total, total, combined} or {remaining, the rest, left, other} is neither lost nor added | "altogether" → "in total" and "remaining" → "left" raised both LOST and ADDED. "left" and "other" are untracked members: they only offset a tracked member's change and never flag alone. |
| "each" | counted | presence only | Source "each … each" rewritten with one "each" flagged as lost. |
| `readable()` | regex-derived names ("addinged") | human cue names ("add") | Display only. |
| `CHUNK_FORMAT` (new) | — | REVIEW when a chunked output has a fact line without a leading "- ", or no "Question:" line | One Haiku chunked output dropped the "- " on its first line. Presentation only. |

Unchanged: the `TARGET_WORDING_CHANGED` overlap threshold (0.5); every REJECT rule for digits; critic and program-mismatch rules.

Known looseness, accepted: "left" and "other" are common words, so a candidate that uses them in another sense ("left hand") can offset a real loss of "remaining". The critic and program layers still run on those items.

### Effect on the dev pilot (re-decided offline, no API calls, $0)

`python src/verify.py data/outputs/anthropic-v1/pilot_generations.jsonl --config config.anthropic.yaml --redecide data/outputs/anthropic-v1/pilot_generations.verify-critic-det-program.jsonl --out data/outputs/anthropic-v1/pilot_generations.verify-critic-det-program.v1_1.jsonl`

| | PASS | REVIEW | REJECT |
|---|---:|---:|---:|
| v1.0 (Nov 2) | 17 | 22 | 1 |
| v1.1 (Nov 11) | 29 | 11 | 0 |

- The RELATIONS_DIFFER-only reviews and the "three ways" REJECT are gone. The "three ways" item is now REVIEW (`NUMBER_WORD_ADDED`, plus "per" added).
- The real catch stays: Haiku-chunked Vikki (`critic:UNSURE`) is still REVIEW.
- One PASS became REVIEW: `haiku55|chunked|gsm8k-train-5510` (`CHUNK_FORMAT`).

These numbers are on the tuning set itself, so they are optimistic by construction. They are checker decisions, not failure rates, and there are no human labels yet. Same-family caveat: the rewriters, critic and extractor are all Claude.

The `--redecide` mode recomputes layer 1 with the current rules and reuses the stored critic and program results. The v1.0 file is kept, and each re-decided row records its old decision in `redecided_from`.
