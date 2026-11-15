"""Small open checker: train a classifier on (source, rewrite) pairs and compare to det-only and the critic (Task H3).

  python src/train_checker.py --run data/outputs/main-v1 [--labels ADJ.csv --key KEY.csv] [--text-backend auto|tfidf|st]
  python src/train_checker.py --synthetic [--out analysis/train_checker.csv]
  python src/train_checker.py --synthetic --level2         # LoRA judge; prints a skip message without torch + CUDA

Level 1 (CPU, always). Features = distill.features (deterministic flags, readability) + text features of the pair:
sentence-transformers embeddings (rewrite - source, |diff|, cosine) if the package is importable and a model can be loaded,
else TF-IDF char and word n-grams (rewrite minus source, vocabulary fitted on the training fold only). Logistic regression
predicts human UNSAFE. Evaluation is leave-source-out (distill's GroupKFold on source_id); the score is thresholded so the
flag rate equals each reference's review rate: det-only REJECT, det-only ANY, the primary critic (not SAFE) and any other
critic supplied as a baseline (e.g. the prompted Qwen critic from Task A2), so recall of UNSAFE is compared at matched rate.

Level 2 (optional, GPU). LoRA fine-tune of a small open Qwen model as a SAFE/UNSAFE judge, leave-source-out, only when
torch with CUDA, transformers and peft are present; otherwise `lora_judge` returns {"status": "skipped", ...} and prints why.
No model is downloaded by the tests. See docs/methods/train_checker.md.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

import distill
from distill import SEED, det_flags, features, top_k_flags

ST_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
QWEN_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


# ------------------------------------------------------------------ text features

def st_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


class PairFeaturizer:
    """Fit on a training fold, transform any rows. backend 'tfidf' (default fallback) or 'st' (embeddings)."""

    def __init__(self, backend: str = "tfidf", max_features: int = 1500, st_model: str = ST_MODEL):
        self.backend, self.max_features, self.st_model = backend, max_features, st_model

    def fit(self, src: list[str], rew: list[str]) -> "PairFeaturizer":
        if self.backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=self.max_features,
                                        sublinear_tf=True).fit(list(src) + list(rew))
            self.word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=self.max_features,
                                        sublinear_tf=True).fit(list(src) + list(rew))
        return self

    def transform(self, src: list[str], rew: list[str]):
        """Sparse (tfidf) or dense (st) matrix of pair features."""
        if self.backend == "tfidf":
            import scipy.sparse as sp
            parts = []
            for v in (self.char, self.word):
                d = v.transform(rew) - v.transform(src)
                parts.append(d)
            return sp.hstack(parts).tocsr()
        a, b = self._embed(src), self._embed(rew)
        cos = (a * b).sum(axis=1, keepdims=True)
        return np.hstack([b - a, np.abs(b - a), cos])

    def _embed(self, texts):
        if not hasattr(self, "_model"):
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.st_model)
        return np.asarray(self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False))


def resolve_backend(choice: str = "auto") -> str:
    """'auto' -> 'st' only if sentence-transformers is importable (it may still need a model download), else 'tfidf'."""
    if choice == "auto":
        return "st" if st_available() else "tfidf"
    if choice == "st" and not st_available():
        print("sentence-transformers not importable; falling back to TF-IDF")
        return "tfidf"
    return choice


# ------------------------------------------------------------------ leave-source-out training

def source_folds(groups: np.ndarray, seed: int = SEED):
    """Yield (train_idx, test_idx) leave-source-out folds (distill's GroupKFold); asserts no source straddles a fold."""
    groups = np.asarray(groups)
    for tr, te in distill._folds(groups, seed).split(np.zeros(len(groups)), None, groups):
        assert not (set(groups[tr]) & set(groups[te])), "source leaked across folds"
        yield tr, te


def _fit_predict(Xd_tr, Xt_tr, y_tr, Xd_te, Xt_te, C: float):
    import scipy.sparse as sp
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(Xd_tr)
    mk = lambda d, t: sp.hstack([sp.csr_matrix(sc.transform(d)), sp.csr_matrix(t)]).tocsr()  # noqa: E731
    clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(mk(Xd_tr, Xt_tr), y_tr)
    return clf.predict_proba(mk(Xd_te, Xt_te))[:, 1]


def leave_source_out_scores(det_X: np.ndarray, src: list[str], rew: list[str], y: np.ndarray, groups: np.ndarray,
                            backend: str = "tfidf", C: float = 0.5, seed: int = SEED, use_text: bool = True,
                            log: list | None = None) -> np.ndarray:
    """Out-of-fold P(UNSAFE). The text featurizer is fitted on each training fold only. `log` (optional list) receives
    (train_sources, test_sources) per fold so callers can audit leakage."""
    p = np.zeros(len(y))
    src, rew = np.asarray(src, dtype=object), np.asarray(rew, dtype=object)
    for tr, te in source_folds(groups, seed):
        if log is not None:
            log.append((set(np.asarray(groups)[tr]), set(np.asarray(groups)[te])))
        if len(set(y[tr])) < 2:
            p[te] = y[tr].mean()
            continue
        if use_text:
            f = PairFeaturizer(backend).fit(list(src[tr]), list(rew[tr]))
            Tt_tr, Tt_te = f.transform(list(src[tr]), list(rew[tr])), f.transform(list(src[te]), list(rew[te]))
        else:
            Tt_tr, Tt_te = np.zeros((len(tr), 0)), np.zeros((len(te), 0))
        p[te] = _fit_predict(det_X[tr], Tt_tr, y[tr], det_X[te], Tt_te, C)
    return p


def fit_eval(verify_rows: list[dict], labels: pd.DataFrame, source_text: dict[str, str], rewrite_text: dict[str, str],
             backend: str = "tfidf", baselines: dict[str, dict[str, int]] | None = None, primary_critic: bool = True,
             seed: int = SEED, C: float = 0.5, fold_log: list | None = None) -> pd.DataFrame:
    """Leave-source-out recall of UNSAFE at matched review rates.

    labels: output_id, source_id, SAFE (1 = safe). source_text: source_id -> text. rewrite_text: output_id -> rewrite.
    baselines: extra critics as {name: {output_id: 1 if flagged (not SAFE)}} (e.g. a prompted Qwen critic).
    Rows: det_only_reject, det_only_any, critic (primary: critic overall != SAFE), each baseline, and the checker
    (text+det) and checker_det_only_features at the review rate of each reference.
    """
    lab = labels.drop_duplicates("output_id")
    by = {r["output_id"]: r for r in verify_rows}
    lab = lab[lab["output_id"].isin(by) & lab["output_id"].isin(rewrite_text) & lab["source_id"].isin(source_text)]
    lab = lab.reset_index(drop=True)
    if lab.empty:
        raise ValueError("no labelled items with verify rows, source text and rewrite text")
    oids, sids = list(lab["output_id"]), list(lab["source_id"])
    unsafe = (1 - lab["SAFE"].astype(int)).to_numpy()
    groups = np.asarray(sids)
    src = [source_text[s] for s in sids]
    rew = [rewrite_text[o] for o in oids]
    det_X = pd.DataFrame([features(by[o], source_text[s]) for o, s in zip(oids, sids)]).to_numpy(float)
    fl = np.array([det_flags(by[o]) for o in oids])
    refs: dict[str, np.ndarray] = {"det_only_reject": fl[:, 0], "det_only_any": fl[:, 1]}
    if primary_critic:
        refs["critic"] = np.array([int(distill.features(by[o], None, True)["critic_SAFE"] == 0) for o in oids])
    for name, d in (baselines or {}).items():
        refs[name] = np.array([int(d.get(o, 1)) for o in oids])
    p_full = leave_source_out_scores(det_X, src, rew, unsafe, groups, backend, C, seed, True, fold_log)
    p_det = leave_source_out_scores(det_X, src, rew, unsafe, groups, backend, C, seed, False)
    out = [distill._row(n, "-", f, unsafe, f.astype(float)) for n, f in refs.items()]
    for n, f in refs.items():
        for tag, p in (("checker", p_full), ("det_features_only", p_det)):
            flag, thr = top_k_flags(p, f.mean(), seed)
            r = distill._row(f"{tag}@matched_{n}", tag, flag, unsafe, p, thr)
            r["recall_minus_reference"] = r["recall_unsafe"] - out[list(refs).index(n)]["recall_unsafe"]
            out.append(r)
    df = pd.DataFrame(out)
    df["backend"] = backend
    return df


# ------------------------------------------------------------------ Level 2: LoRA judge (optional, GPU)

def gpu_stack_status() -> tuple[bool, str]:
    """(ok, reason). ok only if torch with CUDA, transformers and peft are all importable."""
    for mod in ("torch", "transformers", "peft"):
        if importlib.util.find_spec(mod) is None:
            return False, f"{mod} is not installed"
    import torch
    if not torch.cuda.is_available():
        return False, "no CUDA GPU available"
    return True, "ok"


def lora_judge(source_text: list[str], rewrite_text: list[str], y: np.ndarray, groups: np.ndarray,
               model_name: str = QWEN_MODEL, epochs: int = 2, lr: float = 2e-4, r: int = 8, seed: int = SEED,
               max_len: int = 512) -> dict:
    """Leave-source-out LoRA fine-tune of a small Qwen model as a SAFE/UNSAFE sequence classifier (Hu et al. 2021).

    Returns {"status": "skipped", "reason": ...} when the GPU stack is missing (nothing is imported or downloaded),
    else {"status": "ok", "proba": out-of-fold P(UNSAFE)}. Not exercised by the test suite or on CPU-only machines.
    """
    ok, reason = gpu_stack_status()
    if not ok:
        print(f"Level 2 (LoRA judge) skipped: {reason}. Level 1 results above are unaffected.")
        return {"status": "skipped", "reason": reason}
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    texts = [f"Original problem:\n{s}\n\nRewrite:\n{w}\n\nIs the rewrite SAFE (same math, no leaked hints)?"
             for s, w in zip(source_text, rewrite_text)]
    proba = np.zeros(len(y))
    for tr, te in source_folds(groups, seed):
        torch.manual_seed(seed)
        base = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2, torch_dtype=torch.bfloat16)
        base.config.pad_token_id = tok.pad_token_id
        model = get_peft_model(base, LoraConfig(r=r, lora_alpha=2 * r, lora_dropout=0.05, task_type="SEQ_CLS")).cuda()
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
        rng = np.random.default_rng(seed)
        model.train()
        for _ in range(epochs):
            order = rng.permutation(tr)
            for i in range(0, len(order), 8):
                b = order[i:i + 8]
                enc = tok([texts[j] for j in b], return_tensors="pt", padding=True, truncation=True,
                          max_length=max_len).to("cuda")
                loss = model(**enc, labels=torch.tensor(y[b], device="cuda")).loss
                loss.backward()
                opt.step()
                opt.zero_grad()
        model.eval()
        with torch.no_grad():
            for i in range(0, len(te), 16):
                b = te[i:i + 16]
                enc = tok([texts[j] for j in b], return_tensors="pt", padding=True, truncation=True,
                          max_length=max_len).to("cuda")
                proba[b] = torch.softmax(model(**enc).logits.float(), -1)[:, 1].cpu().numpy()
        del model, base, opt
        torch.cuda.empty_cache()
    return {"status": "ok", "proba": proba}


# ------------------------------------------------------------------ synthetic data

_FILLER = "Mia Sam Leo Ana bought sold had read shared apples books pens cards packs boxes on a day at the shop with".split()
_LEAK = ["multiply", "each", "altogether", "subtract", "remaining", "double", "split", "equals", "per", "combine"]


def synthetic(n_sources: int = 120, per_source: int = 5, seed: int = 0):
    """distill.synthetic rows and labels plus texts. UNSAFE rewrites carry 'hint' words the det layer does not flag
    (planted, so text features are informative beyond det flags). Returns labels, verify_rows, source_text, rewrite_text."""
    labels, rows = distill.synthetic(n_sources, per_source, seed)
    rng = np.random.default_rng(seed + 1)
    source_text, rewrite_text = {}, {}
    for sid in labels["source_id"].unique():
        source_text[sid] = " ".join(rng.choice(_FILLER, 25)) + " How many in all?"
    for oid, sid, safe in zip(labels["output_id"], labels["source_id"], labels["SAFE"]):
        words = list(rng.choice(_FILLER, 22))
        if not safe:
            for w in rng.choice(_LEAK, rng.integers(2, 4), replace=False):
                words.insert(int(rng.integers(0, len(words))), str(w))
        elif rng.random() < 0.1:
            words.insert(0, str(rng.choice(_LEAK)))
        rewrite_text[oid] = " ".join(words) + " How many in all?"
    return labels, rows, source_text, rewrite_text


# ------------------------------------------------------------------ cli

def _load_run(run: Path, labels: str | None, key: str | None):
    from common import read_jsonl
    from evaluate import load_source_rows
    df, rows, srcs = distill._load_run(run, labels, key)
    gens = run / "generations.jsonl"
    rewrites = {g["output_id"]: g.get("adapted_problem") or "" for g in read_jsonl(gens)} if gens.exists() else {}
    return df, rows, {s: r.get("text") if isinstance(r, dict) else r for s, r in srcs.items()}, rewrites


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--labels")
    ap.add_argument("--key")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--text-backend", choices=["auto", "tfidf", "st"], default="auto")
    ap.add_argument("--level2", action="store_true", help="also try the LoRA Qwen judge (needs torch+CUDA+peft)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.synthetic:
        df, rows, srcs, rews = synthetic()
        out, backend = (Path(args.out) if args.out else None), ("tfidf" if args.text_backend == "auto" else args.text_backend)
    elif args.run:
        run = Path(args.run)
        df, rows, srcs, rews = _load_run(run, args.labels, args.key)
        out, backend = (Path(args.out) if args.out else run / "analysis" / "train_checker.csv"), resolve_backend(args.text_backend)
    else:
        ap.error("give --run or --synthetic")
    res = fit_eval(rows, df, srcs, rews, backend=backend, seed=args.seed)
    print(f"## Small open checker (level 1, leave-source-out, text backend {backend}): {len(df)} labelled items\n")
    print(distill._md(res))
    if args.level2:
        lab = df.drop_duplicates("output_id")
        lab = lab[lab["output_id"].isin(rews) & lab["source_id"].isin(srcs)]
        r = lora_judge([srcs[s] for s in lab["source_id"]], [rews[o] for o in lab["output_id"]],
                       (1 - lab["SAFE"].astype(int)).to_numpy(), lab["source_id"].to_numpy(), seed=args.seed)
        if r["status"] == "ok":
            lab = lab.assign(p=r["proba"])
            u = (1 - lab["SAFE"].astype(int)).to_numpy()
            for n, rate in (("det_only_reject", res.loc[res.method == "det_only_reject", "flag_rate"].iloc[0]),):
                flag, thr = top_k_flags(r["proba"], rate, args.seed)
                print(distill._md(pd.DataFrame([distill._row(f"lora_qwen@matched_{n}", "lora", flag, u, r["proba"], thr)])))
    if out is not None:
        from evaluate import write_analysis
        p = write_analysis(out.parent, out.stem, res)
        print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
