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
