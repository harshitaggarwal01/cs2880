"""Run: python -m unittest tests.test_phase3_external -v   (offline; mock provider only)

Covers Phase 3A (external-tool import) and 3B (teacher-prompt loader). All files go to temp dirs.
"""
import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import llm  # noqa: E402
from collect_outputs import run as collect_run  # noqa: E402
from common import FROZEN, read_jsonl  # noqa: E402
from import_external import REQUIRED, load_template, to_generations, tool_slug, write_run  # noqa: E402
from realistic_prompts import dedupe_cluster, load_survey, write_prompt_file  # noqa: E402

# keys that exist only on external records (collect_outputs records have none of them)
EXTERNAL_ONLY_KEYS = {"extra"}


class Base(unittest.TestCase):
    def tmp(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        return d


class External(Base):
    def sources(self, n: int = 3) -> list[dict]:
        return read_jsonl(FROZEN / "main.jsonl")[:n]

    def row(self, i: int, src: dict, tool: str = "Fake Tool 1", tos: str = "YES", **kw) -> dict:
        r = {c: "" for c in REQUIRED}
        r.update(external_id=f"t-{i:03d}", tool=tool, tool_version_or_date="2026-11-01", ui_path="Home > Simplify",
                 prompt_used=f"Make this easier:\n\n{src['text']}", source_id=src["source_id"], captured_by="tester",
                 captured_at="2026-11-01T12:00:00Z", raw_response=f"Sure!\n{src['text']}", tos_checked=tos)
        r.update(kw)
        return r

    def write_csv(self, rows: list[dict], name: str = "captures.csv") -> Path:
        path = self.tmp() / name
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, REQUIRED)
            w.writeheader()
            w.writerows(rows)
        return path

    def test_template_loads_and_drops_examples(self):
        template = ROOT / "data" / "external" / "TEMPLATE.csv"
        with open(template, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            raw = list(reader)
        self.assertEqual(reader.fieldnames, REQUIRED)
        self.assertEqual(len(raw), 2)
        self.assertTrue(all(r["external_id"].startswith("EXAMPLE") for r in raw))
        self.assertEqual(load_template(template, allow_unchecked=True), [])
        s = self.sources()
        path = self.write_csv([dict(raw[0]), self.row(1, s[0])])
        rows = load_template(path)
        self.assertEqual([r["external_id"] for r in rows], ["t-001"])
        missing = self.tmp() / "bad.csv"
        missing.write_text("external_id,tool\nx,y\n")
        with self.assertRaises(ValueError):
            load_template(missing)

    def test_unchecked_tos_rejected(self):
        s = self.sources()
        path = self.write_csv([self.row(1, s[0]), self.row(2, s[1], tos="NO")])
        with self.assertRaisesRegex(ValueError, "tos_checked"):
            load_template(path)
        self.assertEqual(len(load_template(path, allow_unchecked=True)), 2)
        with self.assertRaises(ValueError):  # not YES/NO at all
            load_template(self.write_csv([self.row(1, s[0], tos="maybe")]), allow_unchecked=True)
        with self.assertRaises(ValueError):  # two captures for one tool and source
            load_template(self.write_csv([self.row(1, s[0]), self.row(2, s[0])]))

    def test_to_generations_schema_matches_collect_outputs(self):
        cfg = yaml.safe_load((ROOT / "config.example.yaml").read_text())
        cfg["run_id"] = "p3test-schema"
        dev = read_jsonl(FROZEN / "dev.jsonl")[:1]
        out = self.tmp() / "mock.jsonl"
        collect_run(cfg, dev, ["plain"], out, mock=True)
        ref = read_jsonl(out)[0]
        s = self.sources(1)[0]
        gens = to_generations(load_template(self.write_csv([self.row(1, s, tool="Diffit (Fake)")])), run_id="p3test-ext")
        self.assertEqual(len(gens), 1)
        g = gens[0]
        self.assertEqual(set(g) - EXTERNAL_ONLY_KEYS, set(ref))
        self.assertEqual(g["output_id"], f"p3test-ext|diffit_fake|external|{s['source_id']}")
        self.assertEqual((g["generator"], g["transformation"], g["status"], g["provider"]),
                         ("diffit_fake", "external", "EXTERNAL", "external"))
        self.assertEqual((g["dataset"], g["partition"], g["source_sha256"]), (s["dataset"], s["partition"], s["source_sha256"]))
        self.assertEqual(g["extra"]["captured_by"], "tester")
        self.assertEqual(g["adapted_problem"], g["raw_output"])  # blank adapted_problem -> whole reply
        self.assertEqual(g["usage"], {"input_tokens": 0, "output_tokens": 0})
        self.assertEqual(tool_slug("Khanmigo (Teacher Tools)"), "khanmigo_teacher_tools")
        with self.assertRaisesRegex(ValueError, "not found"):
            to_generations([self.row(1, {"source_id": "nope-0", "text": "x"})])

    def test_external_rows_pass_verify_det(self):
        srcs = self.sources(3)
        rows = [self.row(i, s, tool=t) for i, s in enumerate(srcs) for t in ("Tool A", "Tool B")]
        run_dir = self.tmp() / "p3test-verify"
        path = write_run(load_template(self.write_csv(rows)), run_dir)
        self.assertEqual(len(read_jsonl(path)), 6)
        self.assertEqual(yaml.safe_load((run_dir / "config.frozen.yaml").read_text())["origin"], "external")
        write_run(load_template(self.write_csv(rows)), run_dir)  # rerun is append-only: no duplicates
        self.assertEqual(len(read_jsonl(path)), 6)
        subprocess.run([sys.executable, "src/verify.py", str(path), "--config", str(run_dir / "config.frozen.yaml"),
                        "--layers", "det", "--mock"], cwd=ROOT, check=True, capture_output=True, text=True)
        ver = read_jsonl(run_dir / "generations.verify-det.jsonl")
        self.assertEqual({v["output_id"] for v in ver}, {g["output_id"] for g in read_jsonl(path)})
        for v in ver:
            self.assertIn(v["decision"], {"PASS", "REVIEW", "REJECT"})
            self.assertEqual(v["layers"], ["det"])


class TeacherPrompts(Base):
    def test_load_survey_cleans(self):
        path = self.tmp() / "survey.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["role", "prompt_1", "prompt_2"])
            w.writerow(["teacher", "  Simplify this, mail me at a.b@school.org or see https://x.example/y  ", ""])
            w.writerow(["tutor", "", "Make it easier [problem]"])
        got = load_survey(path)
        self.assertEqual(got, ["Simplify this, mail me at [email] or see [link]", "Make it easier [problem]"])

    def test_dedupe_cluster_merges_near_duplicates(self):
        prompts = ["Please simplify this math problem for my students with dyslexia",
                   "Please simplify this math problem for my dyslexia students",
                   "please simplify this math problem for my students with dyslexia.",
                   "Write a haiku about autumn leaves and rain",
                   "Rewrite this word problem using shorter sentences, bullet points and no extra hints"]
        reps = dedupe_cluster(prompts)
        self.assertEqual(len(reps), 3)
        self.assertEqual(len([r for r in reps if "dyslexia" in r]), 1)
        self.assertEqual(len(dedupe_cluster(prompts, threshold=0.999)), 4)  # only the identical-after-normalisation pair merges
        self.assertEqual(dedupe_cluster(["only one"]), ["only one"])
        self.assertEqual(dedupe_cluster([]), [])

    def test_write_prompt_file_parses_with_load_prompt(self):
        d = self.tmp()
        path = write_prompt_file(["Make this easier for a student with ADHD", "Shorter sentences please", "Use bullets"],
                                 version="p3test", out_dir=d)
        self.assertEqual(path.name, "realistic_p3test.txt")
        with mock.patch.object(llm, "PROMPTS", d):
            system, user, sha = llm.load_prompt("realistic_p3test")
        self.assertEqual(system, "You are a helpful assistant.")
        self.assertEqual(user, "Make this easier for a student with ADHD\n\n{problem_text}")
        self.assertEqual(len(sha), 64)
        self.assertEqual(llm.fill(user, problem_text="2+2?").splitlines()[-1], "2+2?")
        self.assertEqual((d / "realistic_p3test_variants.txt").read_text().splitlines(),
                         ["Shorter sentences please", "Use bullets"])
        self.assertNotIn("VARIANTS", path.read_text())
        with self.assertRaises(FileExistsError):
            write_prompt_file(["again"], version="p3test", out_dir=d)
        p2 = write_prompt_file(["Simplify: [problem] thanks"], version="p3b", out_dir=d)
        with mock.patch.object(llm, "PROMPTS", d):
            self.assertEqual(llm.load_prompt("realistic_p3b")[1], "Simplify: {problem_text} thanks")
        self.assertFalse((d / "realistic_p3b_variants.txt").exists())


if __name__ == "__main__":
    unittest.main()
