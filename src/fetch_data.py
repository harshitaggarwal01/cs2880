"""Download the public source datasets into data/raw/ and verify checksums.

  python src/fetch_data.py            # GSM8K (MIT) + ASDiv (CC BY-NC 4.0)
  python src/fetch_data.py --gsm1k    # also GSM1K text for the frozen row indices (needs `datasets`)

GSM1K's Hugging Face card (ScaleAI/gsm1k) declares no license: keep its text
local, do not redistribute it, and confirm terms with the course staff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsm1k", action="store_true")
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


if __name__ == "__main__":
    main()
