"""Two key figures for the Nov 23 video (numbers are the frozen, committed aggregates; no row-level data read).

  python scripts/make_video_figures.py   ->  docs/video/fig_prompt.png, fig_judges.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "video"
OUT.mkdir(parents=True, exist_ok=True)
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, MUTED = "#2a78d6", "#eb6834", "#b8b7b0"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 15, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF})


def clean(ax, grid_axis="x"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


# 1. The prompt decides it: careful vs realistic, checker (main run) and each annotator (practice set)
AQUA = "#1baf7a"
fig, ax = plt.subplots(figsize=(12, 6))
groups = ["Careful prompts", "Prompt teachers type\n(\"make it easier for a student\nwith ADHD or dyslexia\")"]
series = [("Checker REJECT (main run, n = 620 / 300)", BLUE, [82 / 620, 297 / 300], ("82/620", "297/300")),
          ("Humans: unsafe (adjudicated labels, n = 50 / 20)", ORANGE, [4 / 50, 14 / 20], ("4/50", "14/20"))]
h = 0.36
for k, (lab, col, vals, ns) in enumerate(series):
    ys = [1 + (0.5 - k) * (h + 0.02), 0 + (0.5 - k) * (h + 0.02)]
    bars = ax.barh(ys, vals, h, color=col, label=lab)
    for bar, n in zip(bars, ns):
        ax.text(bar.get_width() + 0.012, bar.get_y() + bar.get_height() / 2, f"{bar.get_width():.0%}  ({n})",
                va="center", color=INK, fontsize=14)
ax.set_yticks([1, 0], groups, color=INK, fontsize=15)
ax.set_xlim(0, 1.18)
ax.set_xticks([0, .25, .5, .75, 1], ["0%", "25%", "50%", "75%", "100%"])
clean(ax)
ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.09), ncol=1, frameon=False, fontsize=13, labelcolor=INK2)
fig.suptitle("Same models, same problems: the prompt decides whether the task survives", x=0.02, ha="left", color=INK, fontsize=18)
fig.tight_layout()
fig.savefig(OUT / "fig_prompt.png", dpi=200)
plt.close(fig)

# 2. Judges: catches among the 54 careful-prompt rewrites whose recomputed answer changed
judges = [("GPT-6.1 Sol  ($3.71)", 18, 10), ("Claude Sonnet 5.5  ($7.08)", 16, 7), ("Claude Haiku 5.5  ($0.47)", 13, 7),
          ("GPT-6 Luna  ($0.16)", 12, 9), ("Qwen3 32B  (free)", 7, 3), ("Gemma 3 12B  (free)", 4, 3),
          ("Llama 3.2 3B  (free)", 45, 85)]
fig, ax = plt.subplots(figsize=(12, 6))
names = [j[0] for j in judges][::-1]
vals = [j[1] for j in judges][::-1]
cols = [MUTED if "Llama" in n else BLUE for n in names]
bars = ax.barh(names, vals, color=cols, height=0.62)
for bar, (n, v, flag) in zip(bars, judges[::-1]):
    note = f"{v} of 54   (flags {flag}% of the 620)"
    ax.text(v + 0.6, bar.get_y() + bar.get_height() / 2, note, va="center", color=INK, fontsize=14)
ax.set_xlim(0, 84)
ax.set_xticks([0, 10, 20, 30, 40, 50])
ax.tick_params(axis="y", labelsize=14, labelcolor=INK)
clean(ax)
fig.suptitle("AI judges miss most real errors", x=0.02, ha="left", color=INK, fontsize=18)
ax.set_xlabel("Caught, of the 54 careful-prompt rewrites whose answer verifiably changed", loc="left", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "fig_judges.png", dpi=200)
plt.close(fig)

print("wrote", sorted(p.name for p in OUT.glob("fig_*.png")))
