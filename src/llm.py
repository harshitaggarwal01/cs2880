"""Thin provider wrappers with full logging metadata.

Every call returns a dict with the raw text and everything needed to audit it
later (returned model ID, response ID, token usage, latency, settings).
Settings follow each provider's documented low-variance configuration as of
Oct 2026 (see docs/model_selection.md):
  OpenAI  gpt-6-luna       Responses API, reasoning effort "none", temperature 0
  Google  gemini-3.8-flash thinking_level "low"; no temperature (ignored/removed on 3.8)
  Anthropic claude-sonnet-5-5 (critic) effort "low"; no temperature (400 on 5.x)
  openai_compat  any OpenAI-compatible chat-completions host (OpenRouter, Together, DeepInfra, Groq, Fireworks,
                 the HF router, local vLLM/Ollama). Spec fields: base_url, api_key_env (the NAME of the env var
                 holding the key; never the key), model. Used for open-weight Qwen models.
A "mock" provider is included so the whole pipeline can be dry-run without keys.
"""
from __future__ import annotations

import json
import os
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


THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


class OpenAICompatibleProvider(Provider):
    """Chat-completions provider for OpenAI-compatible hosts.

    JSON output: `settings.json_mode` = "json_schema" (default; response_format json_schema), "json_object"
    (response_format json_object + the schema in the system prompt) or "prompt" (schema in the system prompt only).
    If the host rejects json_schema (HTTP 400/404/422), the call falls back once to json_object; the mode actually
    used is recorded as `json_mode`. Parsed output is validated against the schema (`schema_valid`).
    `settings.extra_body` is passed through (e.g. OpenRouter provider routing {"data_collection": "deny",
    "zdr": true}, or Qwen's {"chat_template_kwargs": {"enable_thinking": false}}). <think> blocks are stripped from
    the returned text and their length logged. A host-reported cost (OpenRouter `usage.cost`) is kept as
    `reported_cost_usd`, and the serving provider, when the host returns one, as `served_by`.
    """
    name = "openai_compat"
    SAMPLING = ("temperature", "top_p", "seed", "presence_penalty", "frequency_penalty")

    def __init__(self, model: str, settings: dict | None = None, base_url: str | None = None,
                 api_key_env: str | None = None, client=None):
        super().__init__(model, settings)
        if not base_url:
            raise ValueError("openai_compat needs base_url")
        self.base_url, self.api_key_env, self._client = base_url, api_key_env, client

    def client(self):
        if self._client is None:
            from openai import OpenAI
            key = None
            if self.api_key_env:
                key = os.environ.get(self.api_key_env)
                if not key:
                    raise RuntimeError(f"environment variable {self.api_key_env} is not set")
            self._client = OpenAI(base_url=self.base_url, api_key=key or "no-key-local", max_retries=0)
        return self._client

    @staticmethod
    def _schema_note(schema: dict) -> str:
        return ("\n\nReply with a single JSON object that matches this JSON schema, and nothing else:\n"
                + json.dumps(schema))

    def _request(self, system: str, user: str, json_schema: dict | None, mode: str):
        kwargs = dict(model=self.model, max_tokens=self.settings.get("max_tokens", 2048))
        kwargs.update({k: self.settings[k] for k in self.SAMPLING if k in self.settings})
        if self.settings.get("extra_body"):
            kwargs["extra_body"] = self.settings["extra_body"]
        sys_text = system
        if json_schema and mode == "json_schema":
            kwargs["response_format"] = {"type": "json_schema",
                                         "json_schema": {"name": "out", "schema": json_schema, "strict": False}}
        elif json_schema:
            sys_text = system + self._schema_note(json_schema)
            if mode == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
        kwargs["messages"] = [{"role": "system", "content": sys_text}, {"role": "user", "content": user}]
        return self.client().chat.completions.create(**kwargs)

    def _call(self, system, user, json_schema):
        mode = self.settings.get("json_mode", "json_schema") if json_schema else "none"
        try:
            r = self._request(system, user, json_schema, mode)
        except Exception as e:  # noqa: BLE001
            if mode == "json_schema" and getattr(e, "status_code", None) in (400, 404, 422):
                mode = "json_object"
                r = self._request(system, user, json_schema, mode)
            else:
                raise
        choice = r.choices[0]
        text = choice.message.content or ""
        think = THINK_RE.findall(text)
        text = THINK_RE.sub("", text).strip()
        u = r.usage
        usage = {"input_tokens": getattr(u, "prompt_tokens", 0) or 0,
                 "output_tokens": getattr(u, "completion_tokens", 0) or 0}  # completion tokens include reasoning
        details = getattr(u, "completion_tokens_details", None)
        if details is not None and getattr(details, "reasoning_tokens", None):
            usage["reasoning_tokens_included"] = details.reasoning_tokens
        extra = {**(getattr(r, "model_extra", None) or {})}
        u_extra = getattr(u, "model_extra", None) or {}
        out = dict(raw_output=text, returned_model=r.model, response_id=r.id, usage=usage,
                   stop_reason=choice.finish_reason, json_mode=mode, think_chars=sum(map(len, think)),
                   base_url=self.base_url)
        if u_extra.get("cost") is not None:
            out["reported_cost_usd"] = float(u_extra["cost"])
        if extra.get("provider"):
            out["served_by"] = extra["provider"]
        if json_schema:
            out["schema_valid"] = _schema_valid(text, json_schema)
        return out


def _schema_valid(text: str, schema: dict) -> bool:
    obj = parse_json_block(text)
    if obj is None:
        return False
    try:
        import jsonschema
        jsonschema.validate(obj, schema)
        return True
    except ImportError:  # pragma: no cover
        return True
    except Exception:  # noqa: BLE001 - jsonschema.ValidationError / SchemaError
        return False


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


PROVIDERS = {"openai": OpenAIProvider, "google": GoogleProvider, "anthropic": AnthropicProvider,
             "openai_compat": OpenAICompatibleProvider, "mock": MockProvider}


def make_provider(spec: dict) -> Provider:
    if "api_key" in spec:
        raise ValueError("put the NAME of an environment variable in api_key_env; never a key in the config")
    cls = PROVIDERS[spec["provider"]]
    if cls is OpenAICompatibleProvider:
        return cls(spec["model"], spec.get("settings", {}), base_url=spec.get("base_url"),
                   api_key_env=spec.get("api_key_env"))
    return cls(spec["model"], spec.get("settings", {}))


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
