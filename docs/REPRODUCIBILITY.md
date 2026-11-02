# Reproducibility

What a clean clone can reproduce, what it cannot, and how to check. Paths are relative to the repository root;
`<run>` is a run id such as `anthropic-v1`.

## 1. Environment
Python 3.13. `python -m pip install -r requirements.txt` (pins are lower bounds; provider SDKs are only needed for real runs).
`python -m unittest discover -s tests -v` is fully offline and includes a mock end-to-end run.

## 2. Data
`python src/fetch_data.py` downloads GSM8K and ASDiv into `data/raw/` and refuses files whose SHA-256 differs from the values
listed in that script (GSM8K test `3730d312…9d14`, ASDiv `ef890406…4929`). GSM1K and GSM-IC text are optional, local-only
downloads (`--gsm1k`, `--gsmic`) and are never part of a release.

## 3. Frozen sample
`python src/sample.py --seed 2880` regenerates `data/frozen/` exactly (10 dev, 100 main, 12 ASDiv, 12 GSM1K ids). Compare the
printed allocation with `data/frozen/MANIFEST.json`, then `git diff --stat data/frozen` should be empty. Never change the seed
once outputs exist.

## 4. Run identity
A run is identified by four things, all stored with it:
- `run_id` (prefix of every `output_id`);
- `data/outputs/<run>/config.frozen.yaml`, whose SHA-256 is recorded in `MANIFEST.json` of the release (`sha256sum` it to check);
- the git commit SHA (`git rev-parse HEAD`, also in `MANIFEST.json`);
- `returned_model`, `response_id`, `prompt_version` and `prompt_sha256` logged on every call.

## 5. Re-running from stored outputs (no API calls)
Everything after generation reads stored files:
```bash
python src/verify.py data/outputs/<run>/generations.jsonl --config data/outputs/<run>/config.frozen.yaml --layers det,critic   # subset layers derived offline
python src/ledger.py --run data/outputs/<run> --config data/outputs/<run>/config.frozen.yaml
python src/evaluate.py --labels data/annotations/<run>/adjudicated.csv --key data/annotations/<run>/KEY_DO_NOT_OPEN.csv \
    --verify data/outputs/<run>/*.verify-*.jsonl --analysis-dir data/outputs/<run>/analysis
python src/report.py --run data/outputs/<run>
python src/conformal.py --run data/outputs/<run> --labels ... --key ...     # likewise cascade.py, ppi.py, policy.py
```
Seeds are fixed in the code (bootstrap 2880, 10,000 replicates), so the analysis CSVs should match to floating-point precision.
Layer subsets are derived from the full verify file, never re-queried.

## 6. Re-running with APIs
`make phase1 CFG=config.anthropic.yaml` (or `python src/run_phase1.py --config ... --until sheets`) runs fetch, generation,
baseline, verification, repair and annotation sheets; each step skips outputs that already exist. Rules: complete generation
inside one week (model ids are not pinned), keep the first response, retry once and only on a technical error, never
regenerate because an output looks bad. Labels are human work and are not part of `make phase1`.

## 7. Checksums
`CHECKSUMS.sha256` holds `sha256  path` for every tracked file except itself, sorted by path. Regenerate and verify:
```bash
git ls-files | grep -v '^CHECKSUMS.sha256$' | LC_ALL=C sort | xargs sha256sum > CHECKSUMS.sha256
sha256sum -c CHECKSUMS.sha256
```

## 8. What is not bit-for-bit reproducible
- **LLM outputs.** Providers may change weights behind an id, and some models accept no temperature. A rerun yields different
  text; the stored generations are the data. `returned_model` shows which model answered.
- **Prices.** `config.frozen.yaml` records the per-token prices used when the run was costed; provider prices change, and one
  Gemini price tier ends 2026-12-31. Ledger totals are therefore a record, not a prediction.
- **Human labels.** Adjudicated labels cannot be regenerated; they are released.

## 9. Release bundle
`python src/release.py --run data/outputs/<run> --out data/release --annotations data/annotations/<run>` (or `make release`)
writes sources, adaptations, verifier rows, labels, aggregate cost, analysis CSVs, the frozen config, prompts, `LICENSES.md`,
`CHECKSUMS.sha256` and `MANIFEST.json`. GSM1K and GSM-IC appear as ids and labels only; red-team and external-tool rows are
omitted. The bundle contains no timestamps of its own, so packaging the same inputs at the same commit reproduces its
`CHECKSUMS.sha256`; the commit SHA in `MANIFEST.json` makes the checksum change when the commit does.
