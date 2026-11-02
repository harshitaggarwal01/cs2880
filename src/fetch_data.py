"""Download the public source datasets into data/raw/ and verify checksums.

  python src/fetch_data.py            # GSM8K (MIT) + ASDiv (CC BY-NC 4.0)
  python src/fetch_data.py --gsm1k    # also GSM1K text for the frozen row indices (needs `datasets`)
  python src/fetch_data.py --gsmic    # also GSM-IC (Shi et al., ICML 2023) -> data/frozen/ext_gsmic.jsonl

GSM1K's Hugging Face card (ScaleAI/gsm1k) declares no license: keep its text
local, do not redistribute it, and confirm terms with the course staff.

GSM-IC (github.com/google-research-datasets/GSM-IC) ships no LICENSE file
either (checked 2026-11-02: the repo holds README.md, the two JSON splits and
gsm8k_validation.jsonl; the README only asks for a citation). The problems are
GSM8K dev problems (MIT) with one distractor sentence added, but the additions
carry no declared license, so treat the file like GSM1K: local only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import urllib.error
import urllib.request
from collections import defaultdict

from common import FROZEN, RAW, sha256_text, tags, write_jsonl

FILES = {
    "gsm8k_train.jsonl": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl",
    "gsm8k_test.jsonl": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl",
    "asdiv.xml": "https://raw.githubusercontent.com/chaochun/nlu-asdiv-dataset/master/dataset/ASDiv.xml",
}
SHA256 = {  # as downloaded 2026-10-16 (GSM8K repo archived read-only on 2026-04-08)
    "gsm8k_test.jsonl": "3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14",
    "asdiv.xml": "ef8904068482919ac48c8eeaaf6df344b8a308ba66d048c2d4d87eab82dc4929",
}

GSMIC_RAW = "https://raw.githubusercontent.com/google-research-datasets/GSM-IC/main/"
GSMIC_FILES = {  # split name -> file; sha256 as downloaded 2026-11-02 (commit 0c1da13, 2023-02-13)
    "2step": ("GSM-IC_2step.json", "0a8c2ae7991feeefb4bc723a4dbd573f1096fcd71670652793bc3a1b3e13408c"),
    "mstep": ("GSM-IC_mstep.json", "152897a5df9ff1aa845a79c47086c88c96d21ff89c4a414f46a783b4a24ca0cf"),
}
GSMIC_STRATA = ("role_label", "number_label", "sentence_label")


def gsmic_distractor(r: dict) -> str:
    """The added irrelevant sentence (the repo stores a template plus its fillers)."""
    if r.get("sentence"):
        return r["sentence"]
    return (r.get("sentence_template") or "").replace("{role}", str(r.get("role", ""))).replace(
        "{number}", str(r.get("number", "")))


def sample_gsmic(rows: list[dict], n: int = 12, seed: int = 2880) -> list[dict]:
    """Deterministic sample of n GSM-IC rows, spread as evenly as possible over
    role_label x number_label x sentence_label, at most one row per original
    question. Rows need `split` and `row` (index within the split) plus the
    repo fields. Rows with an "n/a" label are not used."""
    rng = random.Random(seed)
    cells: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = tuple(r[k] for k in GSMIC_STRATA)
        if "n/a" not in key:
            cells[key].append(r)
    keys = sorted(cells)
    if not keys:
        return []
    # even allocation: n // k each, the remainder to a deterministic random subset of strata
    alloc = {k: n // len(keys) for k in keys}
    for k in rng.sample(keys, n % len(keys)):
        alloc[k] += 1
    picked, used = [], set()
    order = keys[:]
    while sum(alloc.values()) > 0 and order:
        for k in list(order):
            if alloc[k] == 0:
                continue
            pool = [r for r in cells[k] if r["original_question"] not in used]
            if not pool:  # stratum exhausted: hand its quota to the next stratum
                order.remove(k)
                nxt = [o for o in order if o != k]
                if nxt:
                    alloc[nxt[0]] += alloc[k]
                alloc[k] = 0
                continue
            r = rng.choice(sorted(pool, key=lambda x: (x["split"], x["row"])))
            used.add(r["original_question"])
            picked.append(r)
            alloc[k] -= 1
    out = []
    for r in picked:
        text = r["new_question"]
        out.append({
            "source_id": f"gsmic-{r['split']}-{r['row']}", "dataset": "gsmic", "split": r["split"], "row": r["row"],
            "text": text, "answer": str(r["answer"]).replace(",", ""), "original_text": r["original_question"],
            "distractor": gsmic_distractor(r), "partition": "ext_gsmic", "source_sha256": sha256_text(text),
            "tags": tags(text), "n_steps": r.get("n_steps"),
            **{k: r[k] for k in GSMIC_STRATA},
        })
    return out


def fetch_gsmic(n: int, seed: int) -> int:
    """Return 0 on success, 1 if the network blocked the download."""
    try:
        with urllib.request.urlopen(GSMIC_RAW + "LICENSE") as resp:
            print("GSM-IC LICENSE:\n" + resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("GSM-IC: no LICENSE file in the repository (HTTP 404). The README asks for a citation only "
                  "(Shi et al., 2023, arXiv:2302.00093). No license declared: keep the text local, do not redistribute.")
        else:
            print(f"GSM-IC: could not read LICENSE (HTTP {e.code}); treating as no license declared, local only.")
    except (urllib.error.URLError, OSError) as e:
        print(f"GSM-IC: network blocked while reading the LICENSE ({e}). Nothing written.")
        return 1

    rows = []
    for split, (name, expected) in GSMIC_FILES.items():
        path = RAW / name
        if not path.exists():
            try:
                urllib.request.urlretrieve(GSMIC_RAW + name, path)
            except (urllib.error.URLError, OSError) as e:
                print(f"GSM-IC: network blocked while downloading {name} ({e}). Nothing written.")
                return 1
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{name}: {'ok' if digest == expected else 'CHECKSUM MISMATCH - upstream changed'}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rows += [{**r, "split": split, "row": i} for i, r in enumerate(data)]
    sample = sample_gsmic(rows, n=n, seed=seed)
    write_jsonl(FROZEN / "ext_gsmic.jsonl", sample)
    print(f"ext_gsmic.jsonl: {len(sample)} problems (local only; do not redistribute)")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsm1k", action="store_true")
    ap.add_argument("--gsmic", action="store_true", help="GSM-IC distractor problems -> data/frozen/ext_gsmic.jsonl")
    ap.add_argument("--gsmic-n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=2880)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        path = RAW / name
        if not path.exists():
            urllib.request.urlretrieve(url, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        status = "ok" if SHA256.get(name, digest) == digest else "CHECKSUM MISMATCH - upstream changed"
        print(f"{name}: {status}")

    if args.gsm1k:
        from datasets import load_dataset
        ds = load_dataset("ScaleAI/gsm1k", split="test")
        rows = []
        for line in open(FROZEN / "ext_gsm1k_ids.jsonl"):
            r = json.loads(line)
            q = ds[r["row"]]["question"]
            r.update(text=q, answer=ds[r["row"]]["answer"].split("####")[-1].strip(),
                     source_sha256=sha256_text(q), tags=tags(q))
            rows.append(r)
        write_jsonl(FROZEN / "ext_gsm1k.jsonl", rows)
        print(f"ext_gsm1k.jsonl: {len(rows)} problems (local only; do not redistribute)")

    if args.gsmic:
        sys.exit(fetch_gsmic(args.gsmic_n, args.seed))


if __name__ == "__main__":
    main()
