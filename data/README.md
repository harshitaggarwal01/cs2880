# Data

| Path | Content | License / terms |
|---|---|---|
| `raw/gsm8k_{train,test}.jsonl` | GSM8K (Cobbe et al., 2021), from github.com/openai/grade-school-math (archived 2026-04-08) | MIT |
| `raw/asdiv.xml` | ASDiv (Miao et al., ACL 2020), github.com/chaochun/nlu-asdiv-dataset | CC BY-NC 4.0 (non-commercial; attribution) |
| `frozen/dev.jsonl` | 10 GSM8K **train** problems for development and the pilot | MIT |
| `frozen/main.jsonl` | 100 GSM8K **test** problems, stratified (see `MANIFEST.json`) | MIT |
| `frozen/ext_asdiv.jsonl` | 12 ASDiv problems, one per solution type, grades 3–6 | CC BY-NC 4.0 |
| `frozen/ext_gsm1k_ids.jsonl` | 12 GSM1K **row indices only** (Hugging Face `ScaleAI/gsm1k`, test split, 1,205 rows) | No license declared: text is fetched locally by `src/fetch_data.py --gsm1k` and must not be redistributed |
| `frozen/MANIFEST.json` | Seed (2880), allocation, tag coverage | |
| `outputs/<run_id>/` | Append-only generation, verification and repair logs | |
| `annotations/<run_id>/` | Blinded sheets plus key | |

**Checksums** (2026-10-16): GSM8K test `3730d312…9d14`, ASDiv `ef890406…4929`. Full values are in `src/fetch_data.py`.

**Regenerating the sample.** `python src/sample.py --seed 2880` reproduces the frozen files exactly. Do **not** change the seed after outputs exist.
