"""Parsing helpers for skill-doctor.

Stdlib-only. Handles:
  - SKILL.md / agent markdown: split YAML frontmatter from body
  - frontmatter: PyYAML if available, else a conservative scalar fallback that
    covers the keys we actually inspect (name, description, version, etc.)
  - settings.json / installed_plugins.json via json
  - .skill-doctor.toml via tomllib (Python 3.11+)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # optional, nicer parsing when present
    import yaml  # type: ignore
    _HAVE_YAML = True
except Exception:  # pragma: no cover - depends on environment
    _HAVE_YAML = False

try:
    import tomllib  # py3.11+
    _HAVE_TOML = True
except Exception:  # pragma: no cover
    _HAVE_TOML = False


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass
class Document:
    """A parsed markdown document with optional YAML frontmatter."""
    path: Path
    raw: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    fm_present: bool = False
    fm_error: str | None = None

    @property
    def body_lines(self) -> int:
        return self.body.count("\n") + (1 if self.body and not self.body.endswith("\n") else 0)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _fallback_frontmatter(text: str) -> dict[str, Any]:
    """Minimal YAML-subset parser.

    Supports top-level ``key: value`` scalars (optionally quoted) and a single
    level of nesting under a bare ``key:`` mapping. Good enough for the fields
    skill-doctor inspects; it never raises.
    """
    data: dict[str, Any] = {}
    current_map: dict[str, Any] | None = None
    current_key: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        val = _unquote(val)
        if indent == 0:
            if val == "":
                # Could be a nested map; open one.
                current_map = {}
                current_key = key
                data[key] = current_map
            else:
                data[key] = val
                current_map = None
                current_key = None
        elif current_map is not None:
            current_map[key] = val
    # Collapse empty nested maps back to "" so presence checks behave.
    for k, v in list(data.items()):
        if isinstance(v, dict) and not v:
            data[k] = ""
    return data


def _unquote(val: str) -> str:
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    return val


def parse_document(path: Path) -> Document:
    raw = read_text(path)
    m = _FM_RE.match(raw)
    if not m:
        return Document(path=path, raw=raw, body=raw, fm_present=False)
    fm_text = m.group(1)
    body = raw[m.end():]
    fm: dict[str, Any] = {}
    err: str | None = None
    if _HAVE_YAML:
        try:
            loaded = yaml.safe_load(fm_text)
            fm = loaded if isinstance(loaded, dict) else {}
        except Exception as exc:  # malformed YAML is itself a finding
            err = f"YAML parse error: {exc}"
            fm = _fallback_frontmatter(fm_text)
    else:
        fm = _fallback_frontmatter(fm_text)
    return Document(path=path, raw=raw, frontmatter=fm, body=body,
                    fm_present=True, fm_error=err)


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except Exception:
        return None


def load_toml(path: Path) -> dict[str, Any]:
    if not _HAVE_TOML or not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


# Markdown link extraction: [text](target). We only trust explicit markdown
# links — bare prose mentions and URL path segments cause too many false hits.
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Remove fenced code blocks so example snippets don't look like content."""
    return _FENCE_RE.sub("", text)


def find_local_links(body: str) -> list[str]:
    """Return local, relative link targets referenced in markdown body.

    Skips URLs, anchors, mailto, and absolute paths (which can't be resolved
    relative to the skill directory and are usually doc cross-references).
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _MD_LINK_RE.finditer(body):
        t = m.group(1).strip()
        if not t or "://" in t:
            continue
        if t.startswith(("http", "#", "mailto:", "/")):
            continue
        t = t.split("#", 1)[0].strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out
