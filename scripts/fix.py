"""Safe auto-fixers for skill-doctor.

Only ever touches *editable* (authored/project) artifacts, never installed or
third-party skills. Each fixer is conservative and reversible: a timestamped
backup is written before any file changes, and `--dry-run` shows a unified diff
without writing.
"""
from __future__ import annotations

import difflib
import re
import shutil
import time
from pathlib import Path

from rules import Finding, _clean_ws

WIN_PATH_RE = re.compile(r"([\w.-]+)\\([\w.\\-]+)")


def _fix_whitespace(text: str) -> str:
    return _clean_ws(text)


def _fix_winpath(text: str) -> str:
    # Convert backslash paths to forward slashes, line by line, leaving real
    # escapes in fenced shell alone is out of scope — paths are the common case.
    def repl(m: re.Match) -> str:
        return m.group(0).replace("\\", "/")
    return WIN_PATH_RE.sub(repl, text)


FIXERS = {
    "whitespace": _fix_whitespace,
    "winpath": _fix_winpath,
}


def plan_fixes(findings: list[Finding], path_for: dict[str, Path]) -> dict[Path, list[str]]:
    """Map editable file -> list of fix_kind to apply."""
    plan: dict[Path, list[str]] = {}
    for f in findings:
        if not f.autofixable or not f.fix_kind:
            continue
        p = path_for.get(f.artifact)
        if p is None:
            continue
        plan.setdefault(p, [])
        if f.fix_kind not in plan[p]:
            plan[p].append(f.fix_kind)
    return plan


def apply(plan: dict[Path, list[str]], dry_run: bool,
          backup_root: Path) -> tuple[list[str], int]:
    """Apply (or preview) fixes. Returns (diff_chunks, files_changed)."""
    diffs: list[str] = []
    changed = 0
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for path, kinds in sorted(plan.items()):
        try:
            original = path.read_text(encoding="utf-8")
        except Exception:
            continue
        updated = original
        for kind in kinds:
            fixer = FIXERS.get(kind)
            if fixer:
                updated = fixer(updated)
        if updated == original:
            continue
        changed += 1
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path.name}", tofile=f"b/{path.name}"))
        diffs.append(diff)
        if not dry_run:
            backup_dir = backup_root / stamp
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_dir / path.name)
            path.write_text(updated, encoding="utf-8")
    return diffs, changed
