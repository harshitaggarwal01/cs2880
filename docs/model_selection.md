# Model Selection (verified 2026-10-16)

**Sources.**
- Read directly: the official SDK sources on GitHub (`openai-python`, `googleapis/python-genai`), Anthropic's documentation, and Google Cloud's Vertex pricing page.
- From search snippets only (the proxy blocked the pages): items marked **[snippet]**. **Re-check these before the main run.**

| Role | Provider · ID | Low-variance settings | $ / 1M tokens (in / out) | Notes |
|---|---|---|---|---|
| Generator A | OpenAI · `gpt-6-luna` | Responses API, `reasoning={"effort": "none"}`, `temperature=0` | 0.10 / 0.50 [snippet] | Released 2026-09-22 [snippet]. Temperature is accepted **only** with effort `none`. No dated snapshot found: log `response.model`. |
| Generator B | Google · `gemini-3.8-flash` | `thinking_config=ThinkingConfig(thinking_level="low")`; **no** temperature, top_p or top_k | 0.75 / 3.75 until 2026-12-31; 1.50 / 7.50 from 2027-01-01 (confirmed on the Vertex page) | `minimal` thinking level errors on 3.8 [snippet]. Sending both `thinking_level` and `thinking_budget` gives a 400. `max_output_tokens` includes thinking tokens. |
| Critic and extractor | Anthropic · `claude-sonnet-5-5` | `output_config={"effort": "low", "format": {json_schema}}`; no temperature (400 on 5.x) | 2 / 10 | Different family from both generators. No automatic fallback model, so the critic is never silently swapped. |
| Cheap alternatives | `claude-haiku-5-5` (0.10 / 0.50); `gemini-3.5-flash-lite` (0.30 / 2.50, free tier) [snippet]; `gpt-oss-120b` on Vertex (0.09 / 0.36) | | | Use if the budget is tight or a third generator is wanted |

**Why these two generators.** They come from different providers, they are cheap enough for hundreds of calls, and they are the cost-efficient tiers teachers' tools are likely to run on. The study is not "best OpenAI versus best Google".

**Determinism.** Only OpenAI still accepts temperature 0. We keep the **first** response per item, log every call, and report that the outputs are single samples. A small variance check is optional: re-generate 20 main items once and report how much the SAFE label changes.

**Credits.** OpenAI's Researcher Access Program offers up to $1,000 in API credits for academic research (application) [snippet]. The Gemini free tier is too rate-limited for the main run.

**Pilot models are different.** The dev pilot used Claude Haiku/Opus/Sonnet 5.5 through Claude Code subagents (no API keys were available in the environment). This is disclosed everywhere the pilot is cited.

## Open-weight models (Qwen) for the matrix run, verified 2026-11-11

Read directly on 2026-11-11: the OpenRouter model pages and API guides for `qwen/qwen3.8-27b` and `qwen/qwen3.5-9b`, the OpenRouter Qwen model list, the Hugging Face model cards `Qwen/Qwen3.8-27B` and `Qwen/Qwen3.5-9B`, and the OpenRouter privacy, provider-selection, ZDR and usage-accounting docs. Used in `config.matrix.yaml` (run `matrix-v1`).

| Role | Host · ID | Weights · licence | $ / 1M tokens (in / out) | Settings |
|---|---|---|---|---|
| Rewriter `qwen38` and critic `qwen38c` | OpenRouter · `qwen/qwen3.8-27b` | `Qwen/Qwen3.8-27B`, open weights, **Apache-2.0**, released Aug 2026; 27B dense; 262K context | Varies by serving provider: 0.035–0.99 in / 0.42–3.20 out across the 24 listed providers. The config uses the upper bound 0.99 / 3.20; the ledger prefers OpenRouter's reported `usage.cost`. | Thinking is on by default; turned off with `chat_template_kwargs: {enable_thinking: false}` (model card). Rewriter: the card's non-thinking sampling (temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5). Critic: temperature 0. seed 2880. |
| Critic `qwen35_9b` ("runs on a laptop" end) | OpenRouter · `qwen/qwen3.5-9b` | `Qwen/Qwen3.5-9B`, open weights, **Apache-2.0**, Feb 2026; 9B | 0.08–0.17 in / 0.13–0.25 out (6 providers); config uses 0.17 / 0.25 | As above; can instead point `base_url` at a local server, e.g. Ollama `http://localhost:11434/v1`, with no key |

There is no Qwen3.8 model under 10B on OpenRouter or the Qwen Hugging Face page as of Nov 11, so the small model is from the previous generation (Qwen3.5).

**Data use.** OpenRouter's own account training setting "has no bearing on" OpenRouter's own handling of prompts. Its ZDR policy says prompts and responses under ZDR are not retained after processing (with a CSAM-screening exception). Every Qwen request therefore sets `provider: {data_collection: deny, zdr: true}`, so it routes only to providers that do not store or train on inputs and to Zero-Data-Retention endpoints. If none is available, the request fails rather than falling back. Before the first real call, the owner should also turn on the account-level training opt-out in OpenRouter's privacy settings. The served provider is logged per call (`served_by`) when OpenRouter returns it.

**Licence of outputs.** Apache-2.0 places no restriction on redistributing model outputs. Study-problem text keeps its own dataset licence (GSM1K/GSM-IC rows stay local).

**Unverified until the dev pilot:** whether every ZDR provider honours `enable_thinking: false`. The provider logs `think_chars` and `reasoning_tokens_included` per call, so this can be checked on the dev pilot before the main run.

**Key.** `OPENROUTER_API_KEY` in the environment (the config names the variable; it never holds the key).
