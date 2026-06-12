"""Rule engine for skill-doctor.

Each rule maps to a practice in the Skill Maintainer's Codex. Rules produce
Findings; report.py turns them into a report + Setup Health Score.

Rule id prefixes:
  SK  skill authoring        -> category "skills"
  LB  library budget         -> category "skills"
  AG  subagents              -> category "subagents"
  CM  CLAUDE.md / config      -> category "config"
  PM  permissions & hooks    -> category "permissions"
  MT  maintain conventions   -> category "conventions"  (opt-in)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from discovery import Artifact
from parse import (Document, find_local_links, load_json, parse_document,
                   strip_code_fences)

RESERVED_WORDS = ("anthropic", "claude")
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
VAGUE_PHRASES = ("helps with", "does stuff", "various things", "utility for",
                 "helper for", "miscellaneous", "and more")
TRIGGER_SIGNALS = ("use when", "use this", "when the user", "when working",
                   "invoke when", "invoke for", "trigger", "use for")
THIRD_PERSON_BAD = ("i ", "i'll", "i can", "i will", "you can", "you ",
                    "we ", "let me", "i'm")
TIME_RE = re.compile(r"\b(?:before|after|until|as of|since)\b[^.\n]{0,30}\b(?:19|20)\d\d\b",
                     re.IGNORECASE)
TOC_RE = re.compile(r"^#{1,3}\s*(contents|table of contents)", re.IGNORECASE | re.MULTILINE)
WIN_PATH_RE = re.compile(r"[\w.-]+\\[\w.\\-]+")
IMPORT_RE = re.compile(r"(?:^|\s)@([~\w./-]+)")

CATEGORY = {
    "SK": "skills", "LB": "skills", "AG": "subagents",
    "CM": "config", "PM": "permissions", "MT": "conventions",
}


@dataclass
class Finding:
    rule_id: str
    severity: str            # "error" | "warn" | "info"
    message: str
    artifact: str            # display path
    origin: str              # "authored" | "project" | "installed" | "library"
    guide_ref: str
    autofixable: bool = False
    scored: bool = True      # PM summaries don't deduct points
    line: int | None = None
    fix_kind: str | None = None   # hint consumed by fix.py

    @property
    def category(self) -> str:
        return CATEGORY.get(self.rule_id[:2], "skills")


@dataclass
class Context:
    artifacts: list[Artifact]
    conventions: bool = False
    disabled: set[str] = field(default_factory=set)
    only: set[str] = field(default_factory=set)
    budget_chars: int = 15500
    budget_soft: int = 12000
    desc_max: int = 1024
    desc_long: int = 300
    desc_tight: int = 150
    many_skills: int = 40
    # populated during run
    docs: dict[str, Document] = field(default_factory=dict)


def _enabled(ctx: Context, rule_id: str) -> bool:
    if ctx.only:
        return rule_id in ctx.only
    return rule_id not in ctx.disabled


def run(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    skills = [a for a in ctx.artifacts if a.kind == "skill"]
    agents = [a for a in ctx.artifacts if a.kind == "agent"]
    claudemds = [a for a in ctx.artifacts if a.kind == "claudemd"]
    settings = [a for a in ctx.artifacts if a.kind == "settings"]

    for art in skills:
        findings += _skill_rules(ctx, art)
    findings += _library_budget(ctx, skills)
    for art in agents:
        findings += _agent_rules(ctx, art)
    for art in claudemds:
        findings += _claudemd_rules(ctx, art)
    for art in settings:
        findings += _settings_rules(ctx, art)

    # filter disabled / only
    findings = [f for f in findings if _enabled(ctx, f.rule_id)]
    return findings


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #
def _skill_rules(ctx: Context, art: Artifact) -> list[Finding]:
    out: list[Finding] = []
    doc = parse_document(art.path)
    ctx.docs[str(art.path)] = doc
    origin = "library" if art.origin == "installed" else art.origin
    disp = art.label

    def add(rid, sev, msg, guide, autofix=False, fix_kind=None, scored=True):
        out.append(Finding(rid, sev, msg, disp, origin, guide,
                           autofixable=autofix and art.editable,
                           fix_kind=fix_kind, scored=scored))

    fm = doc.frontmatter or {}
    name = str(fm.get("name", "")).strip()
    desc = str(fm.get("description", "")).strip()

    # SK001 name
    if not name:
        # single-file plugin skills may omit name and use folder; only flag if truly absent
        add("SK001", "error", "Missing `name` in frontmatter.", "Part I·04")
    else:
        if not NAME_RE.match(name):
            add("SK001", "error",
                f"`name: {name}` must be lowercase letters/numbers/hyphens, ≤64 chars.",
                "Part I·04")
        if any(w in name.lower() for w in RESERVED_WORDS):
            add("SK001", "warn",
                f"`name: {name}` contains a reserved word ({', '.join(RESERVED_WORDS)}).",
                "Part I·04")

    # SK002 description present + length
    if not desc:
        add("SK002", "error", "Missing `description` in frontmatter.", "Part I·03")
        return out  # nothing more to check without a description body context
    if len(desc) > ctx.desc_max:
        add("SK002", "error",
            f"Description is {len(desc)} chars (max {ctx.desc_max}).", "Part I·03")

    # SK003 third person
    low = desc.lower()
    if any(low.startswith(p) for p in THIRD_PERSON_BAD):
        add("SK003", "warn",
            "Description should be third person (avoid \"I/You/We can…\").", "Part I·03")

    # SK004 vague / missing trigger
    if any(p in low for p in VAGUE_PHRASES):
        add("SK004", "warn", "Description is vague; say what it does + when to use it.",
            "Part I·03")
    elif not any(s in low for s in TRIGGER_SIGNALS):
        add("SK004", "warn",
            "Description has no explicit trigger (add \"Use when …\" + key terms).",
            "Part I·03")

    # SK005 description budget
    nskills = sum(1 for a in ctx.artifacts if a.kind == "skill")
    if len(desc) > ctx.desc_long:
        add("SK005", "warn",
            f"Description is {len(desc)} chars — trim toward ~150 to protect the budget.",
            "Interlude")
    elif len(desc) > ctx.desc_tight and nskills >= ctx.many_skills:
        add("SK005", "warn",
            f"Description {len(desc)} chars with {nskills} skills installed; keep <150.",
            "Interlude")

    # SK006 body length
    if doc.body_lines > 500:
        add("SK006", "warn", f"SKILL.md body is {doc.body_lines} lines (keep <500).",
            "Part I·01")

    body_nc = strip_code_fences(doc.body)

    # reference link rules (SK007/008/009)
    out += _reference_rules(ctx, art, doc, origin)

    # SK010 windows paths
    if WIN_PATH_RE.search(body_nc):
        add("SK010", "warn", "Windows-style backslash path found; use forward slashes.",
            "Part I·10", autofix=True, fix_kind="winpath")

    # SK011 time-sensitive
    if TIME_RE.search(body_nc):
        add("SK011", "info", "Time-sensitive phrasing found; move to an \"old patterns\" note.",
            "Part I·09")

    # SK012 whitespace hygiene
    if doc.raw != _clean_ws(doc.raw):
        add("SK012", "info", "Trailing whitespace or missing final newline.",
            "Part I·01", autofix=True, fix_kind="whitespace")

    # MT conventions (opt-in)
    if ctx.conventions:
        out += _convention_rules(ctx, art, doc, origin)

    return out


def _reference_rules(ctx: Context, art: Artifact, doc: Document, origin: str) -> list[Finding]:
    out: list[Finding] = []
    base = art.path.parent
    for target in find_local_links(strip_code_fences(doc.body)):
        tpath = (base / target).resolve()
        if not tpath.exists():
            out.append(Finding("SK007", "error",
                               f"Broken reference link: {target}", art.label, origin,
                               "Part I·05"))
            continue
        # SK008 one level deep: does the referenced file link further?
        if tpath.suffix == ".md":
            try:
                sub = parse_document(tpath)
                deeper = [t for t in find_local_links(strip_code_fences(sub.body))
                          if (tpath.parent / t).resolve().suffix == ".md"]
                if deeper:
                    out.append(Finding("SK008", "warn",
                                       f"{target} links deeper; keep references one level "
                                       "from SKILL.md.", art.label, origin, "Part I·05"))
                # SK009 ToC for long reference files
                if sub.body_lines > 100 and not TOC_RE.search(sub.body):
                    out.append(Finding("SK009", "info",
                                       f"{target} is {sub.body_lines} lines without a "
                                       "Contents section.", art.label, origin, "Part I·05"))
            except Exception:
                pass
    return out


def _convention_rules(ctx: Context, art: Artifact, doc: Document, origin: str) -> list[Finding]:
    out: list[Finding] = []
    fm = doc.frontmatter or {}
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    has_version = bool(fm.get("version") or (meta or {}).get("version"))
    if not has_version:
        out.append(Finding("MT001", "info", "No version recorded (frontmatter or sidecar).",
                           art.label, origin, "Part IV·19"))
    skill_dir = art.path.parent
    if not any((skill_dir / n).exists() for n in ("CHANGELOG.md", "CHANGELOG")):
        out.append(Finding("MT002", "info", "No CHANGELOG alongside the skill.",
                           art.label, origin, "Part IV·20"))
    has_owner = bool(fm.get("author") or (meta or {}).get("author") or (meta or {}).get("owner"))
    if not has_owner:
        out.append(Finding("MT003", "info", "No owner/author metadata.",
                           art.label, origin, "Part IV·23"))
    return out


def _library_budget(ctx: Context, skills: list[Artifact]) -> list[Finding]:
    total = 0
    for a in skills:
        doc = ctx.docs.get(str(a.path)) or parse_document(a.path)
        fm = doc.frontmatter or {}
        total += len(str(fm.get("name", ""))) + len(str(fm.get("description", ""))) + 40
    if total > ctx.budget_chars:
        return [Finding("LB001", "warn",
                        f"Total skill metadata ~{total} chars exceeds the ~{ctx.budget_chars} "
                        "budget; least-used descriptions may be dropped.",
                        "<library>", "library", "Interlude")]
    if total > ctx.budget_soft:
        return [Finding("LB001", "info",
                        f"Total skill metadata ~{total} chars is approaching the "
                        f"~{ctx.budget_chars} budget.", "<library>", "library", "Interlude")]
    return []


# --------------------------------------------------------------------------- #
# Subagents
# --------------------------------------------------------------------------- #
def _agent_rules(ctx: Context, art: Artifact) -> list[Finding]:
    out: list[Finding] = []
    doc = parse_document(art.path)
    fm = doc.frontmatter or {}
    origin = art.origin
    if not str(fm.get("name", "")).strip():
        out.append(Finding("AG001", "error", "Subagent missing `name`.", art.label,
                           origin, "Part II·12"))
    desc = str(fm.get("description", "")).strip()
    if not desc:
        out.append(Finding("AG001", "error", "Subagent missing `description`.", art.label,
                           origin, "Part II·12"))
    elif len(desc) < 20:
        out.append(Finding("AG003", "warn",
                           "Subagent description too thin for reliable delegation.",
                           art.label, origin, "Part II·12"))
    if not fm.get("tools"):
        out.append(Finding("AG002", "info",
                           "No `tools` declared — grant least privilege explicitly.",
                           art.label, origin, "Part II·12"))
    return out


# --------------------------------------------------------------------------- #
# CLAUDE.md
# --------------------------------------------------------------------------- #
def _claudemd_rules(ctx: Context, art: Artifact) -> list[Finding]:
    out: list[Finding] = []
    text = art.path.read_text(encoding="utf-8", errors="replace")
    lines = text.count("\n") + 1
    if lines > 200:
        out.append(Finding("CM001", "warn",
                           f"{art.label} is {lines} lines (keep <200; use .claude/rules/).",
                           art.label, art.origin, "Part III·15"))
    if lines > 400:
        out.append(Finding("CM003", "info",
                           f"{art.label} is large; split into .claude/rules/ files.",
                           art.label, art.origin, "Part III·15"))
    base = art.path.parent
    for m in IMPORT_RE.finditer(text):
        target = m.group(1)
        if target.startswith("~"):
            continue  # home imports resolved elsewhere
        tpath = (base / target).resolve()
        if not tpath.exists():
            out.append(Finding("CM002", "warn", f"Broken @import: {target}",
                               art.label, art.origin, "Part III·15"))
    return out


# --------------------------------------------------------------------------- #
# Settings: permissions + hooks
# --------------------------------------------------------------------------- #
def _settings_rules(ctx: Context, art: Artifact) -> list[Finding]:
    out: list[Finding] = []
    data = load_json(art.path)
    if not isinstance(data, dict):
        return out
    perms = data.get("permissions") or {}
    allow = perms.get("allow") or []
    deny = perms.get("deny") or []
    ask = perms.get("ask") or []
    hooks = data.get("hooks") or {}

    # PM001 summary (not scored)
    out.append(Finding("PM001", "info",
                       f"Permissions: {len(allow)} allow, {len(deny)} deny, {len(ask)} ask.",
                       art.label, art.origin, "Part III·17", scored=False))

    # PM002 broad allow rules
    broad = [r for r in allow if isinstance(r, str)
             and re.search(r"\(\s*\*\s*\)|\(\s*:\s*\*\s*\)|curl \*|wget \*", r)]
    for r in broad:
        out.append(Finding("PM002", "warn", f"Broad allow rule grants wide access: {r}",
                           art.label, art.origin, "Part IV·22"))

    # PM003 hooks summary + missing matchers
    nhooks = sum(len(v) for v in hooks.values() if isinstance(v, list))
    if nhooks:
        out.append(Finding("PM003", "info", f"{nhooks} hook(s) configured across "
                           f"{len(hooks)} event(s).", art.label, art.origin,
                           "Part II·14", scored=False))
    for event, entries in hooks.items():
        if event in ("PreToolUse", "PostToolUse") and isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict) and not e.get("matcher"):
                    out.append(Finding("PM003", "info",
                                       f"{event} hook has no matcher (runs on every tool).",
                                       art.label, art.origin, "Part II·14"))
    return out


# --------------------------------------------------------------------------- #
# helpers shared with fix.py
# --------------------------------------------------------------------------- #
def _clean_ws(text: str) -> str:
    cleaned = "\n".join(line.rstrip() for line in text.splitlines())
    if not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned
