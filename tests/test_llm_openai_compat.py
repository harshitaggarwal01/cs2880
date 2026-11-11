"""OpenAICompatibleProvider with a fake client (no network)."""
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm import OpenAICompatibleProvider, call_with_one_retry, make_provider  # noqa: E402

SCHEMA = {"type": "object", "properties": {"overall": {"type": "string"}}, "required": ["overall"]}


class HTTPError(Exception):
    def __init__(self, status):
        super().__init__(f"status {status}")
        self.status_code = status


class FakeClient:
    def __init__(self, replies, fail_schema=False, fail_times=0):
        self.calls, self.replies, self.fail_schema, self.fail_times = [], list(replies), fail_schema, fail_times
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        if self.fail_times:
            self.fail_times -= 1
            raise ConnectionError("boom")
        if self.fail_schema and kw.get("response_format", {}).get("type") == "json_schema":
            raise HTTPError(400)
        text = self.replies.pop(0)
        usage = NS(prompt_tokens=11, completion_tokens=7, completion_tokens_details=NS(reasoning_tokens=3),
                   model_extra={"cost": 0.0001})
        return NS(id="gen-1", model="qwen/qwen3.8-27b-20260814", usage=usage, model_extra={"provider": "DeepInfra"},
                  choices=[NS(message=NS(content=text), finish_reason="stop")])


def prov(client, **settings):
    return OpenAICompatibleProvider("qwen/qwen3.8-27b", settings, base_url="https://openrouter.ai/api/v1",
                                    api_key_env="OPENROUTER_API_KEY", client=client)


class OpenAICompat(unittest.TestCase):
    def test_basic_call_and_metadata(self):
        c = FakeClient(['<think>hmm {x}</think>{"overall": "SAFE"}'])
        out = prov(c, temperature=0.7, extra_body={"provider": {"data_collection": "deny", "zdr": True}}).generate(
            "sys", "user", SCHEMA)
        self.assertEqual(out["raw_output"], '{"overall": "SAFE"}')
        self.assertEqual(out["returned_model"], "qwen/qwen3.8-27b-20260814")
        self.assertEqual(out["usage"], {"input_tokens": 11, "output_tokens": 7, "reasoning_tokens_included": 3})
        self.assertEqual(out["stop_reason"], "stop")
        self.assertEqual(out["json_mode"], "json_schema")
        self.assertTrue(out["schema_valid"])
        self.assertEqual(out["reported_cost_usd"], 0.0001)
        self.assertEqual(out["served_by"], "DeepInfra")
        self.assertGreater(out["think_chars"], 0)
        self.assertIn("latency_s", out)
        kw = c.calls[0]
        self.assertEqual(kw["response_format"]["type"], "json_schema")
        self.assertEqual(kw["extra_body"]["provider"]["data_collection"], "deny")
        self.assertEqual(kw["temperature"], 0.7)
        self.assertEqual(kw["messages"][0], {"role": "system", "content": "sys"})

    def test_fallback_to_json_object(self):
        c = FakeClient(['{"overall": "UNSURE"}'], fail_schema=True)
        out = prov(c).generate("sys", "user", SCHEMA)
        self.assertEqual(out["json_mode"], "json_object")
        self.assertEqual(c.calls[-1]["response_format"], {"type": "json_object"})
        self.assertIn(json.dumps(SCHEMA), c.calls[-1]["messages"][0]["content"])
        self.assertTrue(out["schema_valid"])

    def test_invalid_schema_flagged(self):
        out = prov(FakeClient(['{"verdict": 1}'])).generate("s", "u", SCHEMA)
        self.assertFalse(out["schema_valid"])

    def test_prompt_mode_no_response_format(self):
        c = FakeClient(['{"overall": "SAFE"}'])
        prov(c, json_mode="prompt").generate("s", "u", SCHEMA)
        self.assertNotIn("response_format", c.calls[0])

    def test_no_schema_plain_text(self):
        c = FakeClient(["hello"])
        out = prov(c).generate("s", "u")
        self.assertNotIn("response_format", c.calls[0])
        self.assertNotIn("schema_valid", out)

    def test_one_retry_on_technical_failure(self):
        import llm
        sleep, llm.time.sleep = llm.time.sleep, lambda s: None
        try:
            out = call_with_one_retry(prov(FakeClient(['{"overall": "SAFE"}'], fail_times=1)), "s", "u")
            self.assertEqual(out["attempt"], 2)
            out = call_with_one_retry(prov(FakeClient([], fail_times=2)), "s", "u")
            self.assertIsNone(out["raw_output"])
            self.assertIn("ConnectionError", out["error"])
        finally:
            llm.time.sleep = sleep

    def test_missing_key_env_errors(self):
        os.environ.pop("SAFEADAPT_TEST_MISSING_KEY", None)
        p = OpenAICompatibleProvider("m", {}, base_url="https://example.invalid/v1", api_key_env="SAFEADAPT_TEST_MISSING_KEY")
        with self.assertRaises(RuntimeError):
            p.client()

    def test_local_host_needs_no_key(self):
        p = OpenAICompatibleProvider("qwen3.5:9b", {}, base_url="http://localhost:11434/v1")
        self.assertIsNotNone(p.client())  # constructs the SDK client; no network call

    def test_make_provider_and_key_guard(self):
        spec = {"provider": "openai_compat", "model": "qwen/qwen3.8-27b", "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY"}
        p = make_provider(spec)
        self.assertIsInstance(p, OpenAICompatibleProvider)
        self.assertEqual(p.api_key_env, "OPENROUTER_API_KEY")
        with self.assertRaises(ValueError):
            make_provider({**spec, "api_key": "x"})
        with self.assertRaises(ValueError):
            make_provider({"provider": "openai_compat", "model": "m"})


if __name__ == "__main__":
    unittest.main()
