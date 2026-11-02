"""Run: python -m unittest tests.test_phase4 -v   (offline; tiny fake run in a temp dir, no network)"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import failure_gallery  # noqa: E402
import release  # noqa: E402
from common import read_jsonl, write_jsonl  # noqa: E402

GSM1K_TEXT = "SECRET GSM1K PROBLEM TEXT: Mina buys 3 pens at 2 dollars each."
GSM1K_ADAPT = "SECRET GSM1K PARAPHRASE: Mina buys pens."
RUN = "fake-v1"


def gsm1k_row() -> dict:
    return read_jsonl(ROOT / "data" / "frozen" / "ext_gsm1k_ids.jsonl")[0]


def gen(source: dict, generator="gpt", transformation="plain", text="adapted text", **extra) -> dict:
    return {"output_id": f"{RUN}|{generator}|{transformation}|{source['source_id']}", "run_id": RUN,
            "generator": generator, "transformation": transformation, "source_id": source["source_id"],
            "dataset": source["dataset"], "partition": source["partition"], "prompt_version": f"{transformation}_v1",
            "prompt_sha256": "abc", "returned_model": "m-1", "timestamp": "2026-11-02T00:00:00+00:00",
            "raw_output": json.dumps({"adapted_problem": text}), "status": "REWRITTEN", "adapted_problem": text,
            "usage": {"input_tokens": 1, "output_tokens": 1}, **extra}


def verify_row(g: dict, decision="PASS") -> dict:
    return {"output_id": g["output_id"], "raw_output": "", "layers": ["critic", "det", "program"], "decision": decision,
            "reasons": [] if decision == "PASS" else ["QTY_CHANGE: number 7 missing"], "deterministic": {"decision": "PASS"},
            "critic": {"overall": "SAFE", "_meta": {"returned_model": "claude", "usage": {"input_tokens": 5}}},
            "program": {"status": "MATCH"}, "extract_meta": {"source": {"usage": {}}}, "timestamp": "2026-11-02T00:00:00+00:00"}


class Fixture:
    """Fake frozen dir, run dir and annotation dir under one temp root."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.frozen, self.run, self.ann, self.out = tmp / "frozen", tmp / "outputs" / RUN, tmp / "ann", tmp / "release"
        g8 = {"source_id": "gsm8k-test-0001", "dataset": "gsm8k", "split": "test", "row": 1, "partition": "main",
              "text": "Ann has 3 apples and buys 4 more. How many apples does she have?", "answer": "7"}
        asd = {"source_id": "asdiv-nluds-1", "dataset": "asdiv", "split": "all", "row": "nluds-1", "partition": "ext_asdiv",
               "text": "Adam had 14 loads. He washed 8. How many are left?", "answer": "6"}
        k = {**gsm1k_row(), "text": GSM1K_TEXT}
        self.sources = {"gsm8k": g8, "asdiv": asd, "gsm1k": k}
        write_jsonl(self.frozen / "main.jsonl", [g8])
        write_jsonl(self.frozen / "ext_asdiv.jsonl", [asd])
        write_jsonl(self.frozen / "ext_gsm1k.jsonl", [k])          # local full-text file next to the ids file
        self.gens = {n: gen(s) for n, s in self.sources.items()}
        self.gens["gsm1k"]["adapted_problem"] = GSM1K_ADAPT
        self.gens["gsm1k"]["raw_output"] = GSM1K_ADAPT
        self.redteam = gen(g8, generator="redteam:swap", transformation="plain")
        self.external = gen(g8, generator="tool-x", transformation="external")
        write_jsonl(self.run / "generations.jsonl", list(self.gens.values()))
        write_jsonl(self.run / "ablation_generations.jsonl", [self.redteam, self.external])
        write_jsonl(self.run / "generations.verify-critic-det-program.jsonl",
                    [verify_row(g) for g in [*self.gens.values(), self.redteam]])
        (self.run / "config.frozen.yaml").write_text("run_id: fake-v1\n")

    def patch(self):
        return mock.patch.object(release, "FROZEN", self.frozen)

    def write_labels(self) -> None:
        self.ann.mkdir(parents=True, exist_ok=True)
        key, labels = [], []
        for i, (name, g) in enumerate(self.gens.items()):
            aid = f"a{i}"
            key.append({"annotation_id": aid, "output_id": g["output_id"], "source_id": g["source_id"],
                        "generator": g["generator"], "transformation": g["transformation"], "partition": g["partition"],
                        "is_repair": False, "repair_of": "", "double_annotated": False})
            labels.append({"annotation_id": aid, "annotator": "ADJ", "original": "ORIGINAL TEXT", "adaptation": "ADAPT TEXT",
                           "math_fidelity": "PASS", "target_preserved": "PASS", "solvability_changed": "NO",
                           "ambiguity": "NONE", "leakage_level": 0, "leakage_type": "NONE", "presentation": 2,
                           "abstention_appropriate": "", "failure_codes": "", "evidence": f"quote from {name}",
                           "notes": f"note {name}"})
        pd.DataFrame(key).to_csv(self.ann / "KEY_DO_NOT_OPEN.csv", index=False)
        pd.DataFrame(labels).to_csv(self.ann / "adjudicated.csv", index=False)


class ReleaseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fx = Fixture(Path(self._tmp.name))

    def package(self, with_labels=False) -> dict:
        if with_labels:
            self.fx.write_labels()
        with self.fx.patch():
            return release.package(self.fx.run, self.fx.out, self.fx.ann if with_labels else None)

    def test_release_excludes_gsm1k_text(self):
        manifest = self.package(with_labels=True)
        out = self.fx.out
        sources = {r["source_id"]: r for r in read_jsonl(out / "sources.jsonl")}
        k = sources[self.fx.sources["gsm1k"]["source_id"]]
        self.assertIsNone(k["text"])
        self.assertIn("license_note", k)
        self.assertEqual(sources["gsm8k-test-0001"]["license"], "MIT")
        self.assertEqual(sources["gsm8k-test-0001"]["text"], self.fx.sources["gsm8k"]["text"])
        self.assertEqual(len(sources), 3)                                   # ids file and local text file are not doubled

        adapts = read_jsonl(out / "adaptations.jsonl")
        self.assertFalse([a for a in adapts if a["source_id"].startswith("gsm1k")])
        asdiv = next(a for a in adapts if a["source_id"].startswith("asdiv"))
        self.assertEqual(asdiv["attribution"], "ASDiv, Miao, Liang & Su (ACL 2020), CC BY-NC 4.0")
        self.assertIn("raw_output", asdiv)
        self.assertEqual({a["source_id"] for a in adapts}, {"gsm8k-test-0001", "asdiv-nluds-1"})
        for a in adapts:
            self.assertTrue({"output_id", "generator", "transformation", "source_id", "adapted_problem", "status",
                             "prompt_version", "prompt_sha256", "returned_model", "timestamp"} <= set(a))

        ver = read_jsonl(out / "verifier.jsonl")
        self.assertEqual({v["output_id"] for v in ver}, {a["output_id"] for a in adapts})
        for v in ver:
            self.assertNotIn("extract_meta", v)
            self.assertNotIn("_meta", v["critic"])

        labels = pd.read_csv(out / "labels.csv")
        self.assertEqual(len(labels), 3)                                    # labels are ours: gsm1k kept
        self.assertFalse({"original", "adaptation"} & set(labels.columns))
        self.assertTrue(labels["output_id"].str.contains("gsm1k").any())
        gl = labels[labels["output_id"].str.contains("gsm1k")].iloc[0]
        self.assertTrue(pd.isna(gl["evidence"]) or gl["evidence"] == "")    # free text could quote the withheld text
        self.assertEqual(labels[labels["output_id"].str.contains("gsm8k")].iloc[0]["evidence"], "quote from gsm8k")

        # no byte of GSM1K text or paraphrase anywhere in the bundle
        for p in out.rglob("*"):
            if p.is_file():
                body = p.read_text(encoding="utf-8", errors="ignore")
                self.assertNotIn("SECRET GSM1K", body, p.name)

        self.assertEqual(manifest["files"]["sources.jsonl"], {"rows": 3, "text_null": 1})
        self.assertEqual(manifest["files"]["adaptations.jsonl"]["rows"], 2)
        self.assertEqual(manifest["files"]["verifier.jsonl"]["rows"], 2)
        self.assertEqual(manifest["files"]["labels.csv"]["rows"], 3)
        self.assertEqual(manifest["excluded"]["adaptations"]["gsm1k_source"], 1)
        self.assertEqual(manifest["excluded"]["sources_text_withheld"], {"gsm1k": 1})
        on_disk = json.loads((out / "MANIFEST.json").read_text())
        self.assertEqual(on_disk["files"]["adaptations.jsonl"]["rows"], 2)

        listed = {line.split("  ", 1)[1] for line in (out / "CHECKSUMS.sha256").read_text().splitlines()}
        actual = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file() and p.name != "CHECKSUMS.sha256"}
        self.assertEqual(listed, actual)
        for must in ("sources.jsonl", "adaptations.jsonl", "verifier.jsonl", "labels.csv", "MANIFEST.json", "LICENSES.md",
                     "config.frozen.yaml", "prompts/plain_v1.txt"):
            self.assertIn(must, listed)
        self.assertIn("proposed; confirm with team", (out / "LICENSES.md").read_text())

    def test_release_excludes_redteam_and_external(self):
        manifest = self.package()
        adapts = read_jsonl(self.fx.out / "adaptations.jsonl")
        self.assertFalse([a for a in adapts if a["generator"].startswith("redteam:") or a["transformation"] == "external"])
        self.assertEqual(manifest["excluded"]["adaptations"]["redteam_generator"], 1)
        self.assertEqual(manifest["excluded"]["adaptations"]["external_transformation"], 1)
        ids = {v["output_id"] for v in read_jsonl(self.fx.out / "verifier.jsonl")}
        self.assertNotIn(self.fx.redteam["output_id"], ids)                 # its verify row is dropped with it
        self.assertEqual(manifest["files"]["labels.csv"]["rows"], 0)        # no annotations given

    def test_release_is_deterministic_and_rerunnable(self):
        self.package()
        first = (self.fx.out / "CHECKSUMS.sha256").read_text()
        self.package()                                                      # second run over an existing out_dir
        self.assertEqual((self.fx.out / "CHECKSUMS.sha256").read_text(), first)

    def test_raw_output_stripped_for_other_datasets(self):
        other = {"source_id": "mystery-1", "dataset": "mystery", "split": "x", "row": 1, "partition": "ext", "text": "t"}
        write_jsonl(self.fx.frozen / "ext_other.jsonl", [other])
        write_jsonl(self.fx.run / "repairs.jsonl", [gen(other, text="fixed", repair_of="x", raw_output="RAW")])
        self.package()
        rec = next(a for a in read_jsonl(self.fx.out / "adaptations.jsonl") if a["source_id"] == "mystery-1")
        self.assertNotIn("raw_output", rec)
        self.assertEqual(rec["repair_of"], "x")


class GalleryCase(unittest.TestCase):
    def test_failure_gallery_builds(self):
        with tempfile.TemporaryDirectory() as d:
            fx = Fixture(Path(d))
            unsafe = fx.gens["gsm8k"]
            unsafe["adapted_problem"] = "Ann has 3 apples and buys 4 more. First add 3 and 4.\n```odd fence```"
            write_jsonl(fx.run / "generations.jsonl", list(fx.gens.values()))
            write_jsonl(fx.run / "generations.verify-critic-det-program.jsonl",
                        [verify_row(unsafe, "REJECT")] + [verify_row(g) for g in fx.gens.values() if g is not unsafe])
            fx.ann.mkdir()
            rows, key = [], []
            for i, (name, g) in enumerate(fx.gens.items()):
                bad = name in ("gsm8k", "gsm1k")                              # gsm1k item is UNSAFE but must be left out
                rows.append({"annotation_id": f"a{i}", "annotator": "ADJ", "math_fidelity": "PASS", "target_preserved": "PASS",
                             "solvability_changed": "NO", "ambiguity": "NONE", "leakage_level": 2 if bad else 0,
                             "leakage_type": "OPERATION" if bad else "NONE", "presentation": 2, "abstention_appropriate": "",
                             "failure_codes": "LEAK_OPERATION;LEAK_STEPS" if bad else "", "confidence": "HIGH",
                             "evidence": "First add 3 and 4." if bad else "", "notes": ""})
                key.append({"annotation_id": f"a{i}", "output_id": g["output_id"], "source_id": g["source_id"],
                            "generator": g["generator"], "transformation": g["transformation"]})
            pd.DataFrame(rows).to_csv(fx.ann / "adjudicated.csv", index=False)
            pd.DataFrame(key).to_csv(fx.ann / "KEY.csv", index=False)
            out_md = Path(d) / "docs" / "failure_gallery.md"
            with mock.patch.object(failure_gallery, "FROZEN", fx.frozen):
                failure_gallery.build(fx.run, fx.ann / "adjudicated.csv", fx.ann / "KEY.csv", out_md, max_per_code=3)
            md = out_md.read_text()
        self.assertIn(unsafe["output_id"], md)
        self.assertIn(self.original_text(fx), md)
        self.assertIn("First add 3 and 4.", md)
        self.assertIn("```text\n" + fx.sources["gsm8k"]["text"], md)           # fenced original
        self.assertIn("````text\nAnn has 3 apples", md)                         # fence widened around the inner ``` run
        self.assertIn("### OPERATION", md)
        self.assertIn("### LEAK_STEPS", md)
        self.assertIn("**REJECT**", md)
        self.assertIn("QTY_CHANGE", md)
        self.assertIn("prompt_version `plain_v1`", md)
        self.assertNotIn("SECRET GSM1K", md)
        self.assertIn("Excluded: 1 UNSAFE items", md)
        self.assertNotIn(fx.gens["asdiv"]["output_id"], md)                    # SAFE items are not shown

    @staticmethod
    def original_text(fx) -> str:
        return fx.sources["gsm8k"]["text"]


if __name__ == "__main__":
    unittest.main()
