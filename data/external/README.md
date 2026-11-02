# data/external

Manual captures of third-party classroom tools rewriting the frozen source problems (Phase 3A).
Protocol: `docs/external_collection_protocol.md`. Loader: `src/import_external.py`.

| File | Tracked in git? | Contents |
|---|---|---|
| `TEMPLATE.csv` | yes | Column header plus two rows marked `EXAMPLE` (fake tool, fake replies). Copy it, never edit it. |
| `<anything else>.csv` | **no** (git-ignored) | Real captures: one row per tool x source problem, with the full pasted reply. |

## Rules

- **Captured tool outputs are kept local and never redistributed.** Not in git, not in the release, not in the paper's
  appendix. Only human labels and aggregate rates leave this folder. `.gitignore` excludes `data/external/*.csv`
  (except `TEMPLATE.csv`), `data/outputs/external*/` and `data/annotations/external*/`.
- Only the frozen public source problems go into a tool. No student data, no names, no accounts tied to a student.
- Manual capture only: no scraping, no scripted clicks, no API wrappers around a consumer UI.
- Fill `tos_checked` (YES/NO) and `tos_notes` for every row. The loader refuses rows that are not YES unless
  `--allow-unchecked` is passed (local testing only).
- Rows whose `external_id` starts with `EXAMPLE` are dropped on load.

## Columns

`external_id` (unique, e.g. `diffit-001`), `tool`, `tool_version_or_date`, `ui_path` (menu path or mode used),
`prompt_used` (exact text typed, or the tool's fixed option), `source_id` (from `data/frozen/*.jsonl`),
`captured_by`, `captured_at` (ISO 8601), `raw_response` (whole reply, unedited), `adapted_problem` (the part a teacher
would hand to a student; leave blank to use the whole reply), `tos_checked`, `tos_notes`, `notes`.

## Use

```
cp data/external/TEMPLATE.csv data/external/captures.csv     # delete the EXAMPLE rows as you add real ones
python src/import_external.py data/external/captures.csv --run-id external-v1
```
