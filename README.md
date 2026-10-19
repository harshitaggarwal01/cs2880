# SafeAdapt-Math

**Preserving the math while simplifying the words: auditing and verifying LLM accessibility adaptations of math word problems.**
Harvard COMPSCI 2880 (AI for Social Impact), Fall 2026.

## Start here

| If you want… | Read |
|---|---|
| The plan in one page | [`docs/one_page_brief.md`](docs/one_page_brief.md) |
| Real LLM outputs to show the professor | [`docs/professor_examples.md`](docs/professor_examples.md) |
| The full project plan | [`docs/dossier.md`](docs/dossier.md) |
| What to read, in order | [`docs/reading_list.md`](docs/reading_list.md) |
| How to label outputs | [`docs/annotation_guide.md`](docs/annotation_guide.md) |
| What was wrong in the earlier documents | [`docs/source_audit.md`](docs/source_audit.md) |
| Which models and settings, and why | [`docs/model_selection.md`](docs/model_selection.md) |
| The earlier ChatGPT documents (superseded) | [`docs/archive/`](docs/archive/) |

## Status (2026-10-16)
- **Done:**
  - design frozen;
  - 134 source problems sampled and frozen (`data/frozen/`);
  - prompts v1 frozen;
  - real pilot run on the 10 dev problems (`pilot/`, 70 outputs, preliminary labels);
  - code for generation, verification, repair, annotation sheets and analysis;
  - 12 passing tests, including an offline end-to-end run.
- **Next:**
  1. Both teammates re-label the pilot and freeze rubric v1.
  2. Add API keys and run the dev pilot on the real generators.
  3. Run the main generation.

## Quick start
```bash
python -m pip install -r requirements.txt
python src/fetch_data.py                      # GSM8K + ASDiv into data/raw/ (checksums verified)
python -m unittest discover -s tests -v       # all offline; includes a mock end-to-end run

cp config.example.yaml config.yaml            # freeze before the main run
export OPENAI_API_KEY=... GEMINI_API_KEY=... ANTHROPIC_API_KEY=...
python src/collect_outputs.py --config config.yaml --pilot      # dev problems, real generators
python src/collect_outputs.py --config config.yaml              # main + external, plain & chunked
python src/collect_outputs.py --config config.yaml --ablation   # realistic teacher prompt, 100 main problems
python src/baseline.py data/frozen/main.jsonl > data/outputs/main-v1/baseline_main.jsonl
python src/verify.py data/outputs/main-v1/generations.jsonl --config config.yaml
python src/repair.py data/outputs/main-v1/generations.jsonl data/outputs/main-v1/generations.verify-critic-det-program.jsonl
python src/make_annotation_sheets.py data/outputs/main-v1/generations.jsonl data/outputs/main-v1/ablation_generations.jsonl data/outputs/main-v1/repairs.jsonl
python src/evaluate.py --labels <adjudicated.csv> --key data/annotations/main-v1/KEY_DO_NOT_OPEN.csv --verify <verify.jsonl>
```
**Offline dry run.** Add `--mock` to `collect_outputs.py`, `verify.py` or `repair.py`. Mock runs write to `*-mock` folders only.

**GSM1K text.** Run `python src/fetch_data.py --gsm1k` (needs `datasets`). The GSM1K card declares no license, so keep the text local.

## Rules that protect the result
1. Never resample `data/frozen/`. Never touch `main` while developing prompts or the rubric: use `dev`.
2. Keep the first response; retry once on API errors only. Never regenerate because an output looks bad.
3. Annotate blind: do not open `KEY_DO_NOT_OPEN.csv` or verifier outputs until labels are adjudicated.
4. Freeze verifier rules on dev before looking at main labels.
5. The pilot and the constructed stress cases are illustrations. Never quote them as rates.
