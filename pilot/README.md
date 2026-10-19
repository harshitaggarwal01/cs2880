# Dev pilot (2026-10-16)

Real LLM outputs on the 10 frozen dev problems (GSM8K train split), used to answer the professor's request for concrete examples and to calibrate the rubric and checker.

| File | Content |
|---|---|
| `inputs/*.json` | Exact system and user prompt per item, built from `prompts/*_v1.txt` |
| `raw/<model>_<prompt>.jsonl` | Verbatim model responses as written by each generation run |
| `pilot_outputs.jsonl` | Parsed outputs with prompt SHA-256 and status (70 rows) |
| `pilot_checks.jsonl` | Deterministic-layer results (after the refinements described in the dossier, §3) |
| `baseline_dev.jsonl`, `baseline_checks.jsonl` | Deterministic chunking baseline on the same problems |
| `pilot_annotations_PRELIMINARY.csv` | Labels proposed by an AI annotator (Claude) using the rubric. **Must be independently re-labelled by both teammates.** |
| `pilot_evaluation.md` | Output of `src/evaluate.py --pilot` on the preliminary labels |

## Provenance and limitations
- **Models:**
  - Claude Haiku 5.5 and Claude Opus 5.5 ran plain, chunked and naive.
  - Claude Sonnet 5.5 ran plain only. Its chunked and naive runs were stopped by an Anthropic safety classifier (category `reasoning_extraction`, a false positive on a benign task). A partial file from the blocked naive run was deleted, and Opus was used as the second model instead.
- **Generation path:** Claude Code subagents, one session per model × prompt with all 10 items. A harness system prompt was present and sampling was not controlled. This is **not** the main-study API configuration and **not** the main-study models (`gpt-6-luna`, `gemini-3.8-flash`).
- **No rates:** n = 10 problems. Use these outputs as illustrations, not estimates.
