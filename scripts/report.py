"""Reporting + Setup Health Score for skill-doctor.

Turns Findings into a human report (with a scorecard) or JSON. Scoring is
deterministic and driven entirely by documented weights so results are
reproducible and testable.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from rules import Finding

# Documented, configurable weights (no voodoo constants — Codex Practice 10).
SEVERITY_POINTS = {"error": 15, "warn": 5, "info": 1}
SEVERITY_RANK = {"error": 0, "warn": 1, "info": 2}
CATEGORY_WEIGHT = {           # used for the overall weighted mean
    "skills": 4, "config": 2, "subagents": 1, "permissions": 2, "conventions": 1,
}
CATEGORY_LABEL = {
    "skills": "Skills authoring", "config": "CLAUDE.md / config",
    "subagents": "Subagents", "permissions": "Permissions & hooks",
    "conventions": "Maintain conventions",
}
GRADE_BANDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]

# ANSI colour (auto-disabled when not a TTY)
_C = {"error": "\033[31m", "warn": "\033[33m", "info": "\033[90m",
      "head": "\033[1m", "good": "\033[32m", "dim": "\033[90m", "reset": "\033[0m"}


def _color(enabled: bool):
    return _C if enabled else {k: "" for k in _C}


def grade(score: float) -> str:
    for cutoff, letter in GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "F"


@dataclass
class CategoryScore:
    name: str
    score: int
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class Scorecard:
    overall: int
    grade: str
    categories: list[CategoryScore]
    biggest_wins: list[dict[str, Any]]
    library_score: int | None
    library_grade: str | None
    library_note: str


def _deduct(findings: list[Finding], points: dict[str, int]) -> int:
    score = 100
    for f in findings:
        if f.scored:
            score -= points.get(f.severity, 0)
    return max(0, min(100, score))


def compute_score(findings: list[Finding],
                  points: dict[str, int] = SEVERITY_POINTS) -> Scorecard:
    setup = [f for f in findings if f.origin != "library"]
    library = [f for f in findings if f.origin == "library"]

    cats: list[CategoryScore] = []
    weighted_sum = 0.0
    weight_total = 0.0
    for cat in ("skills", "config", "subagents", "permissions", "conventions"):
        cf = [f for f in setup if f.category == cat]
        if not cf and cat == "conventions":
            continue  # only show conventions when present
        sc = _deduct(cf, points)
        counts = {sev: sum(1 for f in cf if f.severity == sev and f.scored)
                  for sev in ("error", "warn", "info")}
        cats.append(CategoryScore(cat, sc, counts))
        w = CATEGORY_WEIGHT.get(cat, 1)
        weighted_sum += sc * w
        weight_total += w
    overall = round(weighted_sum / weight_total) if weight_total else 100

    # biggest wins: scored setup findings ordered by points lost
    scored = [f for f in setup if f.scored and f.severity in points]
    scored.sort(key=lambda f: (-points[f.severity], SEVERITY_RANK[f.severity], f.rule_id))
    wins = [{
        "points": points[f.severity], "rule": f.rule_id, "message": f.message,
        "artifact": f.artifact, "guide_ref": f.guide_ref,
        "fix": "auto-fixable" if f.autofixable else "manual",
    } for f in scored[:5]]

    lib_score = lib_grade = None
    lib_note = ""
    if library or any(f.origin == "library" for f in findings):
        lib_findings = [f for f in findings if f.origin == "library"]
        lib_score = _deduct(lib_findings, points)
        lib_grade = grade(lib_score)
        nbloat = sum(1 for f in lib_findings if f.rule_id == "SK005")
        lib_note = f"{nbloat} bloated description(s)" if nbloat else f"{len(lib_findings)} issue(s)"

    return Scorecard(overall, grade(overall), cats, wins, lib_score, lib_grade, lib_note)


def _bar(score: int, width: int = 14) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def render_scorecard(card: Scorecard, color: bool = True) -> str:
    c = _color(color)
    lines = []
    lines.append(f"  {c['head']}Setup Health{c['reset']}  {_bar(card.overall)}  "
                 f"{card.overall} / 100   ({card.grade})")
    for cat in card.categories:
        label = CATEGORY_LABEL[cat.name]
        dots = "." * max(2, 24 - len(label))
        detail = ""
        if cat.counts.get("error") or cat.counts.get("warn"):
            bits = []
            if cat.counts.get("error"):
                bits.append(f"{cat.counts['error']} error")
            if cat.counts.get("warn"):
                bits.append(f"{cat.counts['warn']} warn")
            detail = f"   {c['dim']}← {', '.join(bits)}{c['reset']}"
        lines.append(f"    {label} {dots} {cat.score:>3}  ({grade(cat.score)}){detail}")
    if card.biggest_wins:
        lines.append(f"  {c['head']}Biggest wins:{c['reset']}")
        for w in card.biggest_wins:
            tag = f"{c['good']}[auto]{c['reset']}" if w["fix"] == "auto-fixable" else "[manual]"
            lines.append(f"    +{w['points']:<2} {w['rule']} {w['message']} "
                         f"— {w['artifact']}  ({w['guide_ref']})  {tag}")
    if card.library_score is not None:
        lines.append(f"  {c['dim']}Installed library health: {card.library_score} / 100 "
                     f"({card.library_grade}) — {card.library_note}{c['reset']}")
    return "\n".join(lines)


def render_findings(findings: list[Finding], min_sev: str = "info",
                    color: bool = True) -> str:
    c = _color(color)
    threshold = SEVERITY_RANK[min_sev]
    # Suppress info-level noise on read-only installed skills — you can't fix them,
    # and they'd bury the findings that matter. They still count toward the score.
    shown = [f for f in findings
             if SEVERITY_RANK[f.severity] <= threshold
             and not (f.origin == "library" and f.severity == "info")]
    hidden = sum(1 for f in findings
                 if f.origin == "library" and f.severity == "info")
    if not shown:
        extra = (f" ({hidden} info-level library notes hidden)" if hidden else "")
        return f"  {c['good']}No findings at or above '{min_sev}'.{c['reset']}{extra}"
    # group by artifact
    by_art: dict[str, list[Finding]] = {}
    for f in shown:
        by_art.setdefault(f.artifact, []).append(f)
    lines = []
    for art in sorted(by_art):
        fs = sorted(by_art[art], key=lambda f: (SEVERITY_RANK[f.severity], f.rule_id))
        origin = fs[0].origin
        suffix = f" {c['dim']}({origin}){c['reset']}" if origin != "authored" else ""
        lines.append(f"\n  {c['head']}{art}{c['reset']}{suffix}")
        for f in fs:
            mark = {"error": "✗", "warn": "▲", "info": "·"}[f.severity]
            col = c[f.severity]
            fixtag = f" {c['good']}[fixable]{c['reset']}" if f.autofixable else ""
            lines.append(f"    {col}{mark} {f.rule_id}{c['reset']} {f.message} "
                         f"{c['dim']}{f.guide_ref}{c['reset']}{fixtag}")
    if hidden:
        lines.append(f"\n  {c['dim']}({hidden} info-level library notes hidden — "
                     f"see --json for the full list){c['reset']}")
    return "\n".join(lines)


def counts(findings: list[Finding]) -> dict[str, int]:
    return {sev: sum(1 for f in findings if f.severity == sev)
            for sev in ("error", "warn", "info")}


def exit_code(findings: list[Finding]) -> int:
    cs = counts(findings)
    if cs["error"]:
        return 2
    if cs["warn"]:
        return 1
    return 0


def to_json(findings: list[Finding], card: Scorecard) -> str:
    payload = {
        "score": {
            "overall": card.overall, "grade": card.grade,
            "categories": {cs.name: {"score": cs.score, "counts": cs.counts}
                           for cs in card.categories},
            "biggest_wins": card.biggest_wins,
            "library": ({"score": card.library_score, "grade": card.library_grade,
                         "note": card.library_note}
                        if card.library_score is not None else None),
        },
        "counts": counts(findings),
        "findings": [{
            "rule": f.rule_id, "severity": f.severity, "category": f.category,
            "message": f.message, "artifact": f.artifact, "origin": f.origin,
            "guide_ref": f.guide_ref, "autofixable": f.autofixable,
        } for f in findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
