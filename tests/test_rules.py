"""Tests for skill-doctor — the eval suite (Codex Practice 02).

Run: python -m pytest tests/
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import discovery  # noqa: E402
import report  # noqa: E402
import rules  # noqa: E402
from discovery import Artifact  # noqa: E402


def _scan_fixture(name, conventions=False):
    """Audit a single bundled fixture skill directly (bypasses ignore rules)."""
    sk = ROOT / "tests/fixtures" / name / "SKILL.md"
    art = Artifact("skill", sk, "project", editable=True, label=name)
    ctx = rules.Context(artifacts=[art], conventions=conventions)
    return rules.run(ctx)


def _scan(paths, ignore=(), conventions=False):
    arts = discovery.discover(scope="project", extra_paths=paths,
                              include_installed=False, ignore=ignore)
    ctx = rules.Context(artifacts=arts, conventions=conventions)
    return rules.run(ctx)


def _ids(findings):
    return {f.rule_id for f in findings}


def test_good_skill_is_clean():
    findings = _scan_fixture("good-skill")
    assert not [f for f in findings if f.severity == "error"]
    card = report.compute_score(findings)
    assert card.grade == "A", (card.overall, _ids(findings))


def test_bad_skill_flags_expected_rules():
    findings = _scan_fixture("bad-skill")
    got = _ids(findings)
    for rid in ("SK001", "SK003", "SK004", "SK007", "SK010", "SK012"):
        assert rid in got, f"expected {rid} in {sorted(got)}"
    assert any(f.severity == "error" for f in findings)


def test_score_is_deterministic():
    findings = _scan_fixture("bad-skill")
    a = report.compute_score(findings)
    b = report.compute_score(findings)
    assert a.overall == b.overall
    assert a.grade == b.grade


def test_biggest_wins_ordered_by_points():
    findings = _scan_fixture("bad-skill")
    wins = report.compute_score(findings).biggest_wins
    pts = [w["points"] for w in wins]
    assert pts == sorted(pts, reverse=True)
    assert wins and wins[0]["points"] == 15  # an error leads


def test_self_compliance_grade_a():
    """skill-doctor must pass its own audit: zero errors, grade A."""
    findings = _scan([ROOT], ignore=["tests/**", "**/.skill-doctor.bak/**"])
    errors = [f for f in findings if f.severity == "error"]
    assert errors == [], [f"{f.rule_id}:{f.artifact}:{f.message}" for f in errors]
    card = report.compute_score(findings)
    assert card.grade == "A", (card.overall, sorted(_ids(findings)))
