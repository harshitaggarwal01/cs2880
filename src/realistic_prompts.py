"""Turn teacher-survey responses into additional "realistic" prompt variants (Phase 3B).

  python src/realistic_prompts.py survey.csv --version v2 [--threshold 0.6]

Reads the free-text prompt columns (prompt_1, prompt_2) of an exported survey CSV, strips emails and
URLs, merges near-duplicates by TF-IDF clustering, and writes
  prompts/realistic_<version>.txt            primary prompt, same ### SYSTEM / ### USER format as naive_v1
  prompts/realistic_<version>_variants.txt   the other cluster representatives, one per line

The variants live in a separate file because llm.load_prompt returns everything after "### USER\\n"
as the user template, so a trailing "### VARIANTS" section would leak into the prompt sent to the model.

Collection must not start before the Harvard CUHS determination (docs/survey/teacher_prompt_survey.md).
Read every prompt for names or school details before committing the files; the regexes only catch
obvious emails and links.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from common import PROMPTS

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)


def deidentify(text: str) -> str:
    return URL.sub("[link]", EMAIL.sub("[email]", text))


def load_survey(csv_path: Path, prompt_cols: tuple[str, ...] = ("prompt_1", "prompt_2")) -> list[str]:
    """Prompts from the given columns: stripped, empties dropped, emails and URLs replaced by placeholders."""
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols = [c for c in prompt_cols if c in (reader.fieldnames or [])]
        if not cols:
            raise ValueError(f"{csv_path}: none of the prompt columns {list(prompt_cols)} found")
        out = []
        for row in reader:
            for c in cols:
                text = deidentify((row.get(c) or "").strip()).strip()
                if text:
                    out.append(text)
    return out


def dedupe_cluster(prompts: list[str], threshold: float = 0.6) -> list[str]:
    """Merge near-duplicates: average-linkage agglomerative clustering on TF-IDF cosine similarity,
    clusters cut where similarity falls below `threshold`. Returns each cluster's medoid (the member with the
    highest mean similarity to the rest), ordered by the first appearance of the cluster in `prompts`."""
    if len(prompts) < 2:
        return list(prompts)
    try:
        x = TfidfVectorizer(lowercase=True, token_pattern=r"(?u)\b\w+\b", ngram_range=(1, 2)).fit_transform(prompts)
    except ValueError:  # nothing but stop-characters: nothing to compare
        return list(dict.fromkeys(prompts))
    sim = (x @ x.T).toarray()  # rows are L2-normalised, so this is cosine similarity
    labels = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="average",
                                     distance_threshold=1.0 - threshold).fit_predict(1.0 - sim)
    reps = []
    for lab in np.unique(labels):
        idx = np.flatnonzero(labels == lab)
        medoid = idx[np.argmax(sim[np.ix_(idx, idx)].mean(axis=1))]  # argmax keeps the earliest on ties
        reps.append((int(idx.min()), prompts[int(medoid)]))
    return [p for _, p in sorted(reps)]


def write_prompt_file(prompts: list[str], version: str = "v2", out_dir: Path = PROMPTS) -> Path:
    """Write prompts/realistic_<version>.txt (first prompt as the USER template) and, if there are more
    prompts, prompts/realistic_<version>_variants.txt. Returns the main file's path. Refuses to overwrite."""
    if not prompts:
        raise ValueError("no prompts to write")
    path = out_dir / f"realistic_{version}.txt"
    variants = out_dir / f"realistic_{version}_variants.txt"
    if path.exists() or variants.exists():
        raise FileExistsError(f"{path.name} already exists; prompt versions are frozen, pick a new --version")
    first = prompts[0].replace("### ", "# ").strip()
    # respondents were asked to write [problem] where the problem goes; otherwise it follows the request
    user = first.replace("[problem]", "{problem_text}") if "[problem]" in first else f"{first}\n\n{{problem_text}}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(f"### SYSTEM\nYou are a helpful assistant.\n\n### USER\n{user}\n", encoding="utf-8")
    if len(prompts) > 1:
        variants.write_text("".join(" ".join(p.split()) + "\n" for p in prompts[1:]), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("survey", help="exported survey CSV with columns prompt_1, prompt_2")
    ap.add_argument("--version", default="v2")
    ap.add_argument("--threshold", type=float, default=0.6, help="cosine similarity above which prompts merge")
    ap.add_argument("--cols", default="prompt_1,prompt_2")
    args = ap.parse_args()
    raw = load_survey(Path(args.survey), tuple(args.cols.split(",")))
    reps = dedupe_cluster(raw, args.threshold)
    path = write_prompt_file(reps, args.version)
    print(f"{len(raw)} prompts -> {len(reps)} after clustering -> {path}")
    print("Read the file for names or school details before committing it.")


if __name__ == "__main__":
    main()
