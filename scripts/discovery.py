"""Artifact discovery for skill-doctor.

Walks the user scope (~/.claude) and a project scope (cwd or --path) to locate
the artifacts skill-doctor audits. Authored artifacts are fixable; installed /
third-party skills are flagged read-only.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

Kind = Literal["skill", "agent", "claudemd", "settings"]

# Always-ignored paths: a tool's own test fixtures and backup dirs are never real
# skills, even when the tool is installed inside ~/.claude/skills.
DEFAULT_IGNORE = [
    "*/tests/fixtures/*",
    "*/.skill-doctor.bak/*",
    "*/__pycache__/*",
]


@dataclass
class Artifact:
    kind: Kind
    path: Path
    origin: str          # "authored" | "installed" | "project"
    editable: bool       # whether `fix` may write to it
    label: str           # short display name


def _home_claude() -> Path:
    return Path(os.path.expanduser("~")) / ".claude"


def _skill_label(skill_md: Path) -> str:
    # .../skills/<name>/SKILL.md  -> <name> ; single-file skill -> parent name
    parent = skill_md.parent
    return parent.name if parent.name not in (".claude", "skills") else skill_md.stem


def _ignored(path: Path, patterns: list[str], roots: list[Path]) -> bool:
    if not patterns:
        return False
    candidates = {path.as_posix(), path.name}
    for root in roots:
        try:
            candidates.add(path.relative_to(root).as_posix())
        except ValueError:
            continue
    for pat in patterns:
        for cand in candidates:
            if fnmatch.fnmatch(cand, pat):
                return True
    return False


def discover(scope: str = "all", extra_paths: Iterable[Path] = (),
             include_installed: bool = True,
             ignore: Iterable[str] = ()) -> list[Artifact]:
    """Return discovered artifacts. scope in {user, project, all}."""
    arts: list[Artifact] = []
    home = _home_claude()

    want_user = scope in ("user", "all")
    want_project = scope in ("project", "all")

    # ---- authored skills (editable) ----
    roots: list[tuple[Path, str]] = []
    if want_user:
        roots.append((home / "skills", "authored"))
    if want_project:
        roots.append((Path.cwd() / ".claude" / "skills", "project"))
    for p in extra_paths:
        roots.append((Path(p), "project"))
        roots.append((Path(p) / ".claude" / "skills", "project"))
        roots.append((Path(p) / "skills", "project"))

    seen: set[Path] = set()
    for root, origin in roots:
        for sk in _find_skill_mds(root):
            rp = sk.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            arts.append(Artifact("skill", sk, origin, editable=True,
                                  label=_skill_label(sk)))

    # ---- installed / third-party skills (read-only) ----
    # The same skill often appears in both plugins/cache and plugins/marketplaces;
    # dedupe by name so it's only audited (and scored) once.
    if include_installed and want_user:
        installed_labels: set[str] = set()
        for base in (home / "plugins" / "cache", home / "plugins" / "marketplaces"):
            for sk in _find_skill_mds(base):
                rp = sk.resolve()
                if rp in seen:
                    continue
                label = _skill_label(sk)
                if label in installed_labels:
                    continue
                seen.add(rp)
                installed_labels.add(label)
                arts.append(Artifact("skill", sk, "installed", editable=False,
                                     label=label))

    # ---- subagents ----
    agent_roots: list[tuple[Path, str, bool]] = []
    if want_user:
        agent_roots.append((home / "agents", "authored", True))
    if want_project:
        agent_roots.append((Path.cwd() / ".claude" / "agents", "project", True))
    for p in extra_paths:
        agent_roots.append((Path(p) / ".claude" / "agents", "project", True))
    for root, origin, editable in agent_roots:
        if root.is_dir():
            for md in sorted(root.glob("*.md")):
                arts.append(Artifact("agent", md, origin, editable=editable,
                                     label=md.stem))

    # ---- CLAUDE.md / rules ----
    cm_candidates: list[tuple[Path, str, bool]] = []
    if want_user:
        cm_candidates.append((home / "CLAUDE.md", "authored", True))
    if want_project:
        cwd = Path.cwd()
        cm_candidates += [
            (cwd / "CLAUDE.md", "project", True),
            (cwd / ".claude" / "CLAUDE.md", "project", True),
            (cwd / "CLAUDE.local.md", "project", True),
        ]
        rules_dir = cwd / ".claude" / "rules"
        if rules_dir.is_dir():
            for md in sorted(rules_dir.glob("**/*.md")):
                cm_candidates.append((md, "project", True))
    for p in extra_paths:
        cm_candidates += [
            (Path(p) / "CLAUDE.md", "project", True),
            (Path(p) / ".claude" / "CLAUDE.md", "project", True),
        ]
    for path, origin, editable in cm_candidates:
        if path.is_file():
            arts.append(Artifact("claudemd", path, origin, editable=editable,
                                 label=str(path.name)))

    # ---- settings (permissions + hooks) ----
    settings_candidates: list[tuple[Path, str]] = []
    if want_user:
        settings_candidates += [
            (home / "settings.json", "authored"),
            (home / "settings.local.json", "authored"),
        ]
    if want_project:
        cwd = Path.cwd()
        settings_candidates += [
            (cwd / ".claude" / "settings.json", "project"),
            (cwd / ".claude" / "settings.local.json", "project"),
        ]
    for path, origin in settings_candidates:
        if path.is_file():
            arts.append(Artifact("settings", path, origin, editable=False,
                                 label=str(path.name)))

    patterns = DEFAULT_IGNORE + list(ignore)
    roots = [Path.cwd(), home] + [Path(p) for p in extra_paths]
    arts = [a for a in arts if not _ignored(a.path, patterns, roots)]

    # Dedupe by resolved path: user and project scopes can resolve to the same
    # file (e.g. when the working directory is the home dir).
    deduped: list[Artifact] = []
    seen_paths: set[Path] = set()
    for a in arts:
        rp = a.path.resolve()
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        deduped.append(a)
    return deduped


def _find_skill_mds(root: Path) -> list[Path]:
    if not root or not root.is_dir():
        return []
    out: list[Path] = []
    # Standard layout: <root>/<name>/SKILL.md  (and deeper for plugin caches)
    for sk in root.rglob("SKILL.md"):
        out.append(sk)
    # Single-file skill: <root>/SKILL.md handled by rglob above.
    return sorted(out)
