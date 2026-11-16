# ollama-v1, dev-pilot attempt 1 (2026-11-15), superseded

Kept as a record; not study data (10 dev problems only). Rows still carry run_id `ollama-v1`.
- Gate FAILED: 19/60 generation parse errors. Gemma3 12B: 9 chunked replies with raw newlines inside JSON strings
  (fixed by `parse_json_block(strict=False)`); Llama3.2 3B: 10/10 chunked replies ignored the JSON format (kept; now
  `tier: cheap`, reported as an outcome).
- Critic qwen3:4b (`qwen_small_c`) kept reasoning despite `reasoning_effort: none`: 2.3k-4k tokens, ~200 s per
  verdict on 4 rows before the job was cancelled; dropped from the config.
- `candidates/`: cheap-rewriter screen on the same 10 dev problems (job 9150591; timed out during qwen3:4b chunked).
- Jobs: 9149674 (smoke), 9150114 (pilot, cancelled after critics), 9150591 (candidates).
