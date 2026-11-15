# Annotation note: hint levels (`prompts/hint_levels_v1.txt`)

Supplement to `docs/annotation_guide.md` (which is unchanged and still governs assessment-mode items). Use this note only for items generated with an `allowed_help` setting. The row records the setting; read it before the leakage pass.

## When hints are intended
| Mode | `allowed_help` | Intended use |
|---|---|---|
| Assessment (tests, benchmarks, anything scored as the learner's own work) | `none` | The learner solves the task unassisted. Any help is a modification. |
| Practice (homework, tutoring, low-stakes work) | `cue`, `worked_step` | Help is part of the activity; it is not scored as unassisted performance. |

Help is never intended inside `adapted_problem`. It belongs only in the separate `help` field.

## What each level permits
- `none`: `help` is empty.
- `cue`: at most one generic reading or attention cue (re-read, find what is asked). No numbers, names, quantities, operations, or statement of which facts matter.
- `worked_step`: exactly one worked first step on the problem's own numbers. No final answer, no later step, no "next, ...".

## Labels: what changes by level
Fidelity, target, solvability and ambiguity are labelled on `adapted_problem` exactly as in the main guide at every level. Leakage is labelled on `adapted_problem` (always) and on `help` (against the permitted level):

| Level | Leakage in `adapted_problem` | Leakage in `help` |
|---|---|---|
| `none` | Main guide, unchanged. Non-empty `help` is a violation: label leakage 2 or 3 as the content warrants and note `help_not_allowed`. | Any content is a violation. |
| `cue` | Main guide, unchanged. Help text inside the problem is level 2 (`STEPS`/`RELEVANCE`). | A compliant generic cue is level 0 here. A cue that names a quantity, operation or relevant fact is level 2. Any intermediate value or answer is level 3. |
| `worked_step` | Main guide, unchanged. | One compliant first step is permitted, not a violation (record `permitted_help`). A second step, the final answer, or a stated plan is level 2 or 3 as in the main guide. |

Rules of thumb:
1. The final answer is level 3 at every level. No setting permits it.
2. Compliant permitted help does not lower the `presentation` score and does not raise `leakage_level` for the adaptation. Report it separately, by `allowed_help`.
3. Do not compare hint-mode items against assessment-mode items for safety rates. They answer different questions.
4. Put the exact span of any violation in `evidence`.

Status: draft v1, not calibrated. No hint-level labels exist yet; calibrate on a small dev set before use.
