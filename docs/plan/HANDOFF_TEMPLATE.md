# Handoff: Phase N (date)

<!-- Fill in every section. Delete these guidance lines once filled. -->

## State
<!-- Branch, commit SHA, run_id, SHA-256 of config.frozen.yaml, and the current test status (pass/fail counts). -->
- Branch: `<branch>`
- Commit SHA: `<sha>`
- run_id: `<run_id>`
- config.frozen.yaml SHA-256: `<sha256>`
- Tests: `<N passed / M failed, from make test>`

## What was run
<!-- One row per pipeline step; mark done only after the output file exists and has been checked. -->

| step | command | output path | done? |
|---|---|---|---|
| generate | `<command>` | `<path>` | `<yes/no>` |
| ablation | `<command>` | `<path>` | `<yes/no>` |
| baseline | `<command>` | `<path>` | `<yes/no>` |
| verify | `<command>` | `<path>` | `<yes/no>` |
| repair | `<command>` | `<path>` | `<yes/no>` |
| sheets | `<command>` | `<path>` | `<yes/no>` |
| ledger | `<command>` | `<path>` | `<yes/no>` |

## Artifacts
<!-- List each artifact with its size on disk and row count (for JSONL/CSV). -->
- `<path>`: `<size>`, `<rows>` rows
- `<path>`: `<size>`, `<rows>` rows

## Known issues / caveats
<!-- Each known bug, data limitation, or interpretation risk, with the affected files. -->
- `<issue and affected files>`

## How to resume
<!-- Exact commands to pick up the run, including any --from/--until bounds. -->
```bash
<command 1>
<command 2>   # e.g. make generate CFG=<config> RUN=<run dir>
```

## Open decisions
<!-- Checkbox list of decisions still needed from the team or PI. -->
- [ ] `<decision>`
- [ ] `<decision>`

## Next owner's first three actions
<!-- Three concrete, ordered first steps for the next owner. -->
1. `<action>`
2. `<action>`
3. `<action>`
