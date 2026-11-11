"""Multi-critic verify, critic specs, ledger columns, primary-file filtering (mock providers; no network)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import primary_verify_files, read_jsonl  # noqa: E402
from ledger import build_ledger  # noqa: E402
from run_phase1 import STEPS  # noqa: E402
from verify import critic_specs, verify_path  # noqa: E402


def dev_source():
    return read_jsonl(ROOT / "data" / "frozen" / "dev.jsonl")[0]


class Specs(unittest.TestCase):
    def test_matrix_config(self):
        cfg = yaml.safe_load(open(ROOT / "config.matrix.yaml"))
        specs, primary = critic_specs(cfg)
        self.assertEqual(primary, "opus55")
        self.assertIn("qwen38c", specs)
        for spec in list(specs.values()) + cfg["generators"]:
            self.assertIn("family", spec)
            self.assertNotIn("api_key", spec)
            if spec["provider"] == "openai_compat":
                self.assertTrue(spec["base_url"].startswith("http"))
                self.assertEqual(spec["settings"]["extra_body"]["provider"]["data_collection"], "deny")
        for g in cfg["generators"] + list(specs.values()):
            self.assertTrue(any(g["model"].startswith(k) for k in cfg["prices"]), g["model"])

    def test_legacy_config(self):
        specs, primary = critic_specs(yaml.safe_load(open(ROOT / "config.anthropic.yaml")))
        self.assertEqual(list(specs), [primary])
        self.assertEqual(specs[primary]["model"], "claude-opus-5-5")

    def test_bad_primary(self):
        with self.assertRaises(ValueError):
            critic_specs({"critics": [{"name": "a"}], "primary_critic": "b"})

    def test_paths(self):
        g = Path("x/generations.jsonl")
        self.assertEqual(verify_path(g, {"det", "critic", "program"}).name, "generations.verify-critic-det-program.jsonl")
        self.assertEqual(verify_path(g, {"det", "critic", "program"}, "qwen38c").name,
                         "generations.verify-critic@qwen38c-det-program.jsonl")

    def test_steps_order(self):
        names = [n for n, _ in STEPS]
        self.assertEqual(names[names.index("verify") + 1], "critics")
        self.assertLess(names.index("critics"), names.index("repair"))


class VerifyAllCritics(unittest.TestCase):
    def test_all_critics_mock(self):
        s = dev_source()
        cfg = yaml.safe_load(open(ROOT / "config.matrix.yaml"))
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            gens = d / "generations.jsonl"
            gens.write_text(json.dumps({"output_id": "t|qwen38|plain|" + s["source_id"], "source_id": s["source_id"],
                                        "generator": "qwen38", "transformation": "plain",
                                        "adapted_problem": s["text"]}) + "\n")
            (d / "cfg.yaml").write_text(yaml.safe_dump(cfg))
            subprocess.run([sys.executable, "src/verify.py", str(gens), "--config", str(d / "cfg.yaml"), "--mock",
                            "--all-critics"], cwd=ROOT, check=True, capture_output=True, text=True)
            files = sorted(p.name for p in d.glob("*.verify-*.jsonl"))
            self.assertEqual(len(files), len(cfg["critics"]))
            prim = read_jsonl(d / "generations.verify-critic-det-program.jsonl")[0]
            self.assertEqual(prim["critic_name"], "opus55")
            q = read_jsonl(d / "generations.verify-critic@qwen38c-det-program.jsonl")[0]
            self.assertEqual((q["critic_name"], q["critic_family"]), ("qwen38c", "alibaba-qwen"))
            self.assertTrue(q["extract_meta"]["source"]["cached"])  # extraction shared via the cache
            self.assertEqual(len(read_jsonl(d / "extractions.jsonl")), 1)  # identical texts -> one extraction
            self.assertEqual([p.name for p in primary_verify_files(d)], ["generations.verify-critic-det-program.jsonl"])
            r = subprocess.run([sys.executable, "src/verify.py", str(gens), "--config", str(d / "cfg.yaml"), "--mock",
                                "--critic", "nope"], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)


class LedgerColumns(unittest.TestCase):
    def test_reported_cost_and_critic_columns(self):
        cfg = yaml.safe_load(open(ROOT / "config.matrix.yaml"))
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            g = {"output_id": "o1", "generator": "qwen38", "transformation": "plain", "partition": "dev",
                 "returned_model": "qwen/qwen3.8-27b-20260814", "usage": {"input_tokens": 1000, "output_tokens": 1000},
                 "reported_cost_usd": 0.0002}
            (d / "generations.jsonl").write_text(json.dumps(g) + "\n")
            meta = {"returned_model": "qwen/qwen3.8-27b", "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}
            v = {"output_id": "o1", "critic": {"overall": "SAFE", "_meta": meta}, "critic_name": "qwen38c",
                 "critic_family": "alibaba-qwen", "extract_meta": {}}
            (d / "generations.verify-critic@qwen38c-det-program.jsonl").write_text(json.dumps(v) + "\n")
            led = build_ledger(d, cfg)
            gen = led[led["stage"] == "gen"].iloc[0]
            self.assertEqual((gen["usd"], gen["cost_source"], gen["family"]), (0.0002, "reported", "alibaba-qwen"))
            crit = led[led["stage"] == "critic"].iloc[0]
            self.assertEqual((crit["critic_name"], crit["family"], crit["cost_source"]),
                             ("qwen38c", "alibaba-qwen", "price_table"))
            self.assertAlmostEqual(crit["usd"], 0.99)  # 1M input tokens at the conservative table price

    def test_legacy_run_still_loads(self):
        cfg = yaml.safe_load(open(ROOT / "config.anthropic.yaml"))
        run = ROOT / "data" / "outputs" / "anthropic-v1"
        with tempfile.TemporaryDirectory() as d:
            for f in ("pilot_generations.jsonl", "pilot_generations.verify-critic-det-program.jsonl", "extractions.jsonl"):
                (Path(d) / f).write_bytes((run / f).read_bytes())
            led = build_ledger(Path(d), cfg)
            self.assertAlmostEqual(led["usd"].sum(), 1.19, delta=0.01)
            self.assertTrue((led[led["stage"] == "critic"]["critic_name"] == "primary").all())


if __name__ == "__main__":
    unittest.main()
