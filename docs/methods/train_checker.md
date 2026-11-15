# Small open checker (`src/train_checker.py`)

**Purpose.** `distill.py` asks what the deterministic layer's own evidence can recover. This module adds the text of the
pair, so the classifier can see what the rules cannot: hint-like wording, changed phrasing, drifted content. It is
distillation in the loose sense of Hinton, Vinyals and Dean (2015), with human labels as the target, and it follows the
rule-then-judge pattern of Zhao, Knezevic and Kaser (2026). Goal: a free or near-free checker whose recall of UNSAFE is
compared with the det-only layer and with the primary critic at the same review rate.

**Level 1 (CPU, always).**
- *Features:* everything in `distill.features` (flag one-hots, counts, readability deltas) plus pair text features.
  With `sentence-transformers` importable: embedding of the rewrite minus that of the source, its absolute value, and their
  cosine (model `all-MiniLM-L6-v2`, downloaded on first real use; never in the tests). Otherwise TF-IDF character (3-5)
  and word (1-2) n-grams, rewrite minus source, vocabulary fitted on the training fold only.
- *Model:* class-balanced logistic regression on standardised deterministic features and the text features.
- *Evaluation:* leave-source-out `GroupKFold` on `source_id` (distill's folds; an assertion checks no source is in both
  train and test of a fold). The out-of-fold score is thresholded so the flag rate equals the review rate of each
  reference: det-only REJECT, det-only ANY, the primary critic (not SAFE), and any extra critic passed as a baseline
  (the prompted Qwen critic from Task A2 is the zero-training baseline). We report recall of UNSAFE, precision, AUPRC and
  the difference from the reference. A `det_features_only` ablation shows what the text features add.

**Level 2 (optional, GPU).** LoRA (Hu et al., 2021) fine-tune of a small open Qwen model (default
`Qwen2.5-0.5B-Instruct`) as a SAFE/UNSAFE sequence classifier on (source, rewrite, label) triples, leave-source-out. It
runs only if torch with CUDA, transformers and peft are importable; otherwise `lora_judge` prints the reason and returns
`{"status": "skipped"}`. The Level 2 code path is not exercised by the tests or on CPU-only machines.

**Limitations.**
- A few hundred labelled items and few UNSAFE cases: differences of a few points are noise. No confidence interval is
  reported yet; use a source-clustered bootstrap (`evaluate.cluster_boot`) on the out-of-fold scores before quoting.
- At the det-only REJECT rate the rules are already precise, so the checker can at best tie there; the interesting rows are
  the ANY and critic rates.
- Text features can learn generator-specific style rather than harm. Report per-generator recall, and test on a held-out
  generator before claiming transfer to other tools.
- Hyperparameters are defaults; any search needs nested leave-source-out.
- TF-IDF difference features are lexical; they catch added hint words, not subtle semantic drift. The critic and the
  program check remain the backstop.

**References.**
- Hinton, Vinyals, Dean (2015). Distilling the knowledge in a neural network. arXiv:1503.02531.
- Zhao, Knezevic, Kaser (2026). Evaluating Answer Leakage Robustness of LLM Tutors. *ACL* (as cited in `distill.md`).
- Hu, Shen, Wallis, Allen-Zhu, Li, Wang, Wang, Chen (2021). LoRA: Low-rank adaptation of large language models. arXiv:2106.09685.
