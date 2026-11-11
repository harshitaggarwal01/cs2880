"""Phase 1 orchestrator: fetch -> pilot -> generate -> ablation -> baseline -> verify -> repair -> ... -> report.

  python src/run_phase1.py --config config.yaml --list                    # show the steps
  python src/run_phase1.py --config config.yaml                           # run everything not yet done
  python src/run_phase1.py --config config.yaml --from verify --until sheets
  python src/run_phase1.py --config config.example.yaml --mock            # offline dry run (*-mock folders)
  python src/run_phase1.py --config config.yaml --from verify --force     # redo steps even if marked done

Each finished step leaves data/outputs/<run_id>/.done/<step>; reruns skip marked steps (the
underlying scripts are append-only and resume on their own, so --force is also safe).
config.frozen.yaml is written once per run and never overwritten unless --force.
The evaluate step waits for data/annotations/<run_id>/adjudicated.csv (human labels); report runs in
pipeline-only mode until then.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import yaml

from baseline import records
from collect_outputs import sources
from common import OUTPUTS, ROOT, append_jsonl
from llm import done_ids

FULL = "verify-critic-det-program"  # suffix verify.py gives a full-layer verify file


class Ctx:
    def __init__(self, cfg_path: str, cfg: dict, mock: bool):
        self.cfg_path, self.cfg, self.mock = cfg_path, cfg, mock
        self.run_dir = OUTPUTS / cfg["run_id"]
        self.ann_dir = ROOT / "data" / "annotations" / cfg["run_id"]

    def sh(self, script: str, *args: str, mock_flag: bool = True) -> str:
        cmd = [sys.executable, f"src/{script}", *args]
        if self.mock and mock_flag:
            cmd.append("--mock")
        try:
            return subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True).stdout
        except subprocess.CalledProcessError as e:
            print((e.stdout or "")[-2000:] + (e.stderr or "")[-2000:], file=sys.stderr)
            raise

    def path(self, name: str) -> Path:
        return self.run_dir / name


# Step functions return None when done, or a string reason when skipped (no marker is written then).

def fetch(c: Ctx) -> str | None:
    if c.mock:
        return "mock run uses the frozen sources only"
    c.sh("fetch_data.py", mock_flag=False)


def pilot(c: Ctx) -> None:
    c.sh("collect_outputs.py", "--config", c.cfg_path, "--pilot")


def generate(c: Ctx) -> None:
    c.sh("collect_outputs.py", "--config", c.cfg_path)


def ablation(c: Ctx) -> None:
    c.sh("collect_outputs.py", "--config", c.cfg_path, "--ablation")


def baseline(c: Ctx) -> None:
    out = c.path("baseline.jsonl")
    seen = done_ids(out)
    for row in records(sources(c.cfg["partitions"]), c.cfg["run_id"]):
        if row["output_id"] not in seen:
            append_jsonl(out, row)


def _existing(c: Ctx, *names: str) -> list[Path]:
    return [c.path(n) for n in names if c.path(n).exists()]


def verify(c: Ctx) -> None:
    for gens in _existing(c, "generations.jsonl", "ablation_generations.jsonl"):
        c.sh("verify.py", str(gens), "--config", c.cfg_path)
    for gens in _existing(c, "baseline.jsonl"):
        c.sh("verify.py", str(gens), "--config", c.cfg_path, "--layers", "det")


def critics(c: Ctx) -> str | None:
    """Run the non-primary critics of a matrix config (`critics:` list). Decisions stay per critic; repair and the
    prespecified analysis use the primary critic only."""
    if not c.cfg.get("critics"):
        return "single-critic config"
    others = [k["name"] for k in c.cfg["critics"] if k["name"] != c.cfg["primary_critic"]]
    if not others:
        return "only the primary critic is configured"
    for gens in _existing(c, "generations.jsonl", "ablation_generations.jsonl"):  # same files as the verify step
        for name in others:
            c.sh("verify.py", str(gens), "--config", c.cfg_path, "--critic", name)


def repair(c: Ctx) -> None:
    for gens in _existing(c, "generations.jsonl", "ablation_generations.jsonl"):
        ver = gens.with_name(f"{gens.stem}.{FULL}.jsonl")
        if ver.exists():
            c.sh("repair.py", str(gens), str(ver), "--config", c.cfg_path)


def verify_repairs(c: Ctx) -> str | None:
    reps = _existing(c, "repairs.jsonl")
    if not reps:
        return "no repairs were needed"
    c.sh("verify.py", str(reps[0]), "--config", c.cfg_path)


def sheets(c: Ctx) -> None:
    files = _existing(c, "generations.jsonl", "ablation_generations.jsonl", "baseline.jsonl", "repairs.jsonl")
    c.sh("make_annotation_sheets.py", *map(str, files), mock_flag=False)


def ledger(c: Ctx) -> None:
    print(c.sh("ledger.py", "--run", str(c.run_dir), "--config", c.cfg_path, mock_flag=False))


def _need_labels(c: Ctx) -> str | None:
    if not (c.ann_dir / "adjudicated.csv").exists():
        return f"waiting for {(c.ann_dir / 'adjudicated.csv').relative_to(ROOT)}"
    return None


def evaluate(c: Ctx) -> str | None:
    if reason := _need_labels(c):
        return reason
    ver = _existing(c, f"generations.{FULL}.jsonl", f"ablation_generations.{FULL}.jsonl",
                    "baseline.verify-det.jsonl", f"repairs.{FULL}.jsonl")
    print(c.sh("evaluate.py", "--labels", str(c.ann_dir / "adjudicated.csv"), "--key",
               str(c.ann_dir / "KEY_DO_NOT_OPEN.csv"), "--verify", *map(str, ver),
               "--analysis-dir", str(c.run_dir / "analysis"), mock_flag=False))


def report(c: Ctx) -> str | None:
    # report.py auto-detects adjudicated labels; without them it writes the pipeline-only report
    if not (ROOT / "src" / "report.py").exists():
        return "src/report.py not found"
    print(c.sh("report.py", "--run", str(c.run_dir), mock_flag=False))


STEPS: list[tuple[str, Callable[[Ctx], str | None]]] = [
    ("fetch", fetch), ("pilot", pilot), ("generate", generate), ("ablation", ablation), ("baseline", baseline),
    ("verify", verify), ("critics", critics), ("repair", repair), ("verify_repairs", verify_repairs), ("sheets", sheets),
    ("ledger", ledger), ("evaluate", evaluate), ("report", report),
]


def run(cfg_path: str, from_step: str | None = None, until_step: str | None = None, mock: bool = False,
        force: bool = False) -> None:
    names = [n for n, _ in STEPS]
    for s in (from_step, until_step):
        if s is not None and s not in names:
            raise SystemExit(f"unknown step {s!r}; choose from {', '.join(names)}")
    lo = names.index(from_step) if from_step else 0
    hi = names.index(until_step) if until_step else len(names) - 1
    cfg = yaml.safe_load(Path(cfg_path).read_text())
    if mock:  # same suffix as collect_outputs: dry runs never touch the real run's folders
        cfg["run_id"] += "-mock"
    c = Ctx(cfg_path, cfg, mock)
    c.run_dir.mkdir(parents=True, exist_ok=True)
    frozen = c.path("config.frozen.yaml")
    if force or not frozen.exists():
        frozen.write_text(yaml.safe_dump(cfg, sort_keys=False))
    done_dir = c.path(".done")
    done_dir.mkdir(exist_ok=True)

    for i, (name, fn) in enumerate(STEPS[lo: hi + 1], start=lo + 1):
        marker, t0 = done_dir / name, time.time()
        if marker.exists() and not force:
            status = "skipped (already done)"
        else:
            reason = fn(c)
            status = f"skipped ({reason})" if reason else "done"
            if not reason:
                marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
        print(f"[{i}/{len(STEPS)}] {name:<15} {status}  {time.time() - t0:.1f}s")


def main() -> None:
    names = [n for n, _ in STEPS]
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--from", dest="from_step", choices=names)
    ap.add_argument("--until", dest="until_step", choices=names)
    ap.add_argument("--mock", action="store_true", help="offline dry run with the mock provider")
    ap.add_argument("--force", action="store_true", help="rerun steps even if marked done")
    ap.add_argument("--list", action="store_true", help="print the steps and exit")
    args = ap.parse_args()
    if args.list:
        for i, n in enumerate(names, 1):
            print(f"{i:>2}. {n}")
        return
    run(args.config, args.from_step, args.until_step, args.mock, args.force)


if __name__ == "__main__":
    main()
