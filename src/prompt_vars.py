"""Prompt loading with extra placeholders (e.g. {target_language}, {allowed_help}).

llm.fill already substitutes any keyword by str.replace, so extra placeholders work; this helper adds
validation on top, without touching llm.py:

  from prompt_vars import render_prompt
  system, user, sha = render_prompt("hint_levels_v1", problem_text="...", allowed_help="cue")
  system, user, sha = render_prompt("translate_plain_v1", problem_text="...", target_language="Spanish")

Placeholders are substituted in both the system and the user part. Unfilled {name} placeholders (identifiers
only, so JSON braces in the prompts are safe) raise ValueError. allowed_help must be one of ALLOWED_HELP.
"""
from __future__ import annotations

import re

from llm import fill, load_prompt

ALLOWED_HELP = ("none", "cue", "worked_step")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render_prompt(name: str, **kw: str) -> tuple[str, str, str]:
    """Return (system, user, sha256) with all placeholders filled; the sha is of the unfilled prompt file."""
    if "allowed_help" in kw and kw["allowed_help"] not in ALLOWED_HELP:
        raise ValueError(f"allowed_help must be one of {ALLOWED_HELP}, got {kw['allowed_help']!r}")
    system, user, sha = load_prompt(name)
    system, user = fill(system, **kw), fill(user, **kw)
    # values may themselves contain braces (problem text), so check placeholders before substitution
    missing = {m for t in load_prompt(name)[:2] for m in _PLACEHOLDER.findall(t)} - set(kw)
    if missing:
        raise ValueError(f"prompt {name!r} has unfilled placeholders: {sorted(missing)}")
    return system, user, sha
