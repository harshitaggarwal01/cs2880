"""Thin provider wrappers with full logging metadata.

Every call returns a dict with the raw text and everything needed to audit it
later (returned model ID, response ID, token usage, latency, settings).
Settings follow each provider's documented low-variance configuration as of
Oct 2026 (see docs/model_selection.md):
  OpenAI  gpt-6-luna       Responses API, reasoning effort "none", temperature 0
  Google  gemini-3.8-flash thinking_level "low"; no temperature (ignored/removed on 3.8)
  Anthropic claude-sonnet-5-5 (critic) effort "low"; no temperature (400 on 5.x)
A "mock" provider is included so the whole pipeline can be dry-run without keys.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from common import PROMPTS, sha256_text


def load_prompt(name: str) -> tuple[str, str, str]:
    """Return (system, user_template, sha256) for prompts/<name>.txt."""
    raw = (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")
    system, user = raw.split("### USER\n", 1)
    return system.replace("### SYSTEM\n", "").strip(), user.strip(), sha256_text(raw)


def fill(template: str, **kw: str) -> str:
    # str.replace rather than str.format: prompts contain literal JSON braces
    for k, v in kw.items():
        template = template.replace("{" + k + "}", v)
    return template


def parse_json_block(text: str) -> dict | None:
    """Parse the first JSON object in a model reply (tolerates ```json fences)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class Provider:
    name = "base"

    def __init__(self, model: str, settings: dict | None = None):
        self.model = model
        self.settings = settings or {}

    def generate(self, system: str, user: str, json_schema: dict | None = None) -> dict:
        t0 = time.time()
        out = self._call(system, user, json_schema)
        out.update(provider=self.name, requested_model=self.model, settings=self.settings,
                   latency_s=round(time.time() - t0, 3),
                   timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return out

    def _call(self, system: str, user: str, json_schema: dict | None) -> dict:  # pragma: no cover
        raise NotImplementedError


class OpenAIProvider(Provider):
    name = "openai"

    def _call(self, system, user, json_schema):
        from openai import OpenAI
        client = getattr(self, "_client", None) or OpenAI()
        self._client = client
        kwargs = dict(model=self.model, instructions=system, input=user,
                      max_output_tokens=self.settings.get("max_output_tokens", 1024))
        effort = self.settings.get("reasoning_effort", "none")
        kwargs["reasoning"] = {"effort": effort}
        if effort == "none" and "temperature" in self.settings:  # temperature only allowed with effort "none"
            kwargs["temperature"] = self.settings["temperature"]
        if json_schema:
            kwargs["text"] = {"format": {"type": "json_schema", "name": "out", "schema": json_schema, "strict": False}}
        r = client.responses.create(**kwargs)
        u = r.usage
        return dict(raw_output=r.output_text, returned_model=r.model, response_id=r.id,
                    usage={"input_tokens": u.input_tokens, "output_tokens": u.output_tokens}, stop_reason=r.status)


class GoogleProvider(Provider):
    name = "google"

    def _call(self, system, user, json_schema):
        from google import genai
        from google.genai import types
        client = getattr(self, "_client", None) or genai.Client()
        self._client = client
        cfg = dict(system_instruction=system,
                   thinking_config=types.ThinkingConfig(thinking_level=self.settings.get("thinking_level", "low")),
                   max_output_tokens=self.settings.get("max_output_tokens", 2048))  # cap includes thinking tokens
        if json_schema:
            cfg.update(response_mime_type="application/json", response_json_schema=json_schema)
        r = client.models.generate_content(model=self.model, contents=user, config=types.GenerateContentConfig(**cfg))
        um = r.usage_metadata
        return dict(raw_output=r.text or "", returned_model=getattr(r, "model_version", None),
                    response_id=getattr(r, "response_id", None),
                    usage={"input_tokens": um.prompt_token_count, "output_tokens": um.candidates_token_count,
                           "thinking_tokens": getattr(um, "thoughts_token_count", None)},
                    stop_reason=str(r.candidates[0].finish_reason) if r.candidates else None)


class AnthropicProvider(Provider):
    name = "anthropic"

    def _call(self, system, user, json_schema):
        import anthropic
        client = getattr(self, "_client", None) or anthropic.Anthropic()
        self._client = client
        output_config: dict = {"effort": self.settings.get("effort", "low")}
        if json_schema:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        # No server-side model fallback: a silent model switch would confound the study.
        r = client.messages.create(model=self.model, max_tokens=self.settings.get("max_tokens", 4096), system=system,
                                   messages=[{"role": "user", "content": user}], output_config=output_config)
        text = "" if r.stop_reason == "refusal" else next((b.text for b in r.content if b.type == "text"), "")
        return dict(raw_output=text, returned_model=r.model, response_id=r.id,
                    usage={"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens},
                    stop_reason=r.stop_reason)


class MockProvider(Provider):
    """Offline stand-in: returns the source problem unchanged (or a SAFE critic verdict)."""
    name = "mock"

    def _call(self, system, user, json_schema):
        src = re.search(r"<<<\n(.*?)\n>>>", user, re.S)
        # prompts without delimiters (the realistic teacher prompt) put the problem after the last blank line
        text = src.group(1) if src else user.strip().split("\n\n")[-1]
        if "audit an accessibility adaptation" in system:
            out = json.dumps({"math_fidelity": "PASS", "target_preserved": "PASS", "instructional_leakage": "NONE",
                              "ambiguity_introduced": "NO", "failure_codes": [], "evidence": [], "overall": "SAFE"})
        elif "structured representation" in system:
            nums = re.findall(r"\d+(?:\.\d+)?", text)
            out = json.dumps({"quantities": [{"value": n} for n in nums], "relations": [], "conditions": [],
                              "target": {}, "program": "+".join(nums) or "0"})
        elif "You fix an accessibility adaptation" in system:
            out = json.dumps({"adapted_problem": text, "changes": []})
        else:
            out = json.dumps({"status": "NO_REWRITE_NEEDED", "adapted_problem": text})
        return dict(raw_output=out, returned_model="mock", response_id=None, usage={"input_tokens": 0, "output_tokens": 0},
                    stop_reason="end")


PROVIDERS = {"openai": OpenAIProvider, "google": GoogleProvider, "anthropic": AnthropicProvider, "mock": MockProvider}


def make_provider(spec: dict) -> Provider:
    return PROVIDERS[spec["provider"]](spec["model"], spec.get("settings", {}))


def call_with_one_retry(provider: Provider, system: str, user: str, json_schema: dict | None = None) -> dict:
    """One prespecified retry on technical/API failure only - never on content."""
    for attempt in (1, 2):
        try:
            out = provider.generate(system, user, json_schema)
            out["attempt"] = attempt
            return out
        except Exception as e:  # noqa: BLE001 - provider SDKs raise many types
            err = f"{type(e).__name__}: {e}"
            if attempt == 2:
                return dict(raw_output=None, error=err, attempt=attempt, provider=provider.name,
                            requested_model=provider.model, settings=provider.settings,
                            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            time.sleep(5)
    raise AssertionError("unreachable")


def done_ids(path: Path, key: str = "output_id") -> set[str]:
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return {json.loads(l)[key] for l in f if l.strip() and json.loads(l).get("raw_output") is not None}
