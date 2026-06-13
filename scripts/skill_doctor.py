#!/usr/bin/env python3
"""skill-doctor engine — invoked by the /skill-doctor Claude skill.

This is the internal engine the skill runs inside a Claude Code session; it is
not a standalone CLI you install or run by hand. Stdlib only. Subcommands:

  scan      audit + scorecard (writes nothing)
  fix       apply safe auto-fixes to authored artifacts
  rules     print the rule catalog

Claude drives these on your behalf when you invoke /skill-doctor. Exit codes
from `scan`: 0 = clean, 1 = warnings, 2 = errors.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discovery  # noqa: E402
import fix as fixmod  # noqa: E402
import report  # noqa: E402
import rules  # noqa: E402
from parse import load_toml  # noqa: E402

RULE_CATALOG = [
    ("SK001", "error", "name present, lowercase-hyphen, ≤64, no reserved words", "Part I·04"),
    ("SK002", "error", "description present and ≤1024 chars", "Part I·03"),
    ("SK003", "warn", "description written in third person", "Part I·03"),
    ("SK004", "warn", "description not vague; has explicit trigger", "Part I·03"),
    ("SK005", "warn", "description within metadata budget", "Interlude"),
    ("SK006", "warn", "SKILL.md body under 500 lines", "Part I·01"),
    ("SK007", "error", "internal reference links resolve", "Part I·05"),
    ("SK008", "warn", "references kept one level deep", "Part I·05"),
    ("SK009", "info", "long reference files have a Contents section", "Part I·05"),
    ("SK010", "warn", "no Windows-style backslash paths [auto-fix]", "Part I·10"),
    ("SK011", "info", "no time-sensitive phrasing", "Part I·09"),
    ("SK012", "info", "no trailing whitespace / final newline [auto-fix]", "Part I·01"),
    ("LB001", "warn", "total skill metadata within the ~15.5k budget", "Interlude"),
    ("AG001", "error", "subagent has name + description", "Part II·12"),
    ("AG002", "info", "subagent declares tools (least privilege)", "Part II·12"),
    ("AG003", "warn", "subagent description is delegation-ready", "Part II·12"),
    ("CM001", "warn", "CLAUDE.md under 200 lines", "Part III·15"),
    ("CM002", "warn", "@imports resolve", "Part III·15"),
    ("CM003", "info", "very long CLAUDE.md split into rules", "Part III·15"),
    ("PM001", "info", "permissions summary", "Part III·17"),
    ("PM002", "warn", "no over-broad allow rules", "Part IV·22"),
    ("PM003", "info", "hooks summary / matchers", "Part II·14"),
    ("MT001", "info", "version recorded (opt-in)", "Part IV·19"),
    ("MT002", "info", "CHANGELOG present (opt-in)", "Part IV·20"),
    ("MT003", "info", "owner/author recorded (opt-in)", "Part IV·23"),
]


def _build_context(args) -> rules.Context:
    cfg = load_toml(Path.cwd() / ".skill-doctor.toml")
    rcfg = cfg.get("rules", {}) if isinstance(cfg, dict) else {}
    scfg = cfg.get("score", {}) if isinstance(cfg, dict) else {}
    extra = [Path(p) for p in (args.path or [])]
    ignore = cfg.get("ignore", []) if isinstance(cfg, dict) else []
    arts = discovery.discover(
        scope=args.scope, extra_paths=extra,
        include_installed=not args.skip_installed, ignore=ignore)
    disabled = set(rcfg.get("disable", [])) | set(_split(getattr(args, "disable", None)))
    only = set(_split(getattr(args, "only", None)))
    ctx = rules.Context(
        artifacts=arts,
        conventions=getattr(args, "conventions", False),
        disabled=disabled, only=only,
        budget_chars=int(scfg.get("budget_chars", 15500)),
    )
    return ctx, scfg


def _split(val) -> list[str]:
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


def _use_color(args) -> bool:
    if getattr(args, "no_color", False):
        return False
    return sys.stdout.isatty()


def cmd_scan(args) -> int:
    ctx, scfg = _build_context(args)
    findings = rules.run(ctx)
    points = {
        "error": int(scfg.get("error", report.SEVERITY_POINTS["error"])),
        "warn": int(scfg.get("warn", report.SEVERITY_POINTS["warn"])),
        "info": int(scfg.get("info", report.SEVERITY_POINTS["info"])),
    }
    card = report.compute_score(findings, points)
    color = _use_color(args)

    if args.json:
        print(report.to_json(findings, card))
    elif args.score_only:
        print(report.render_scorecard(card, color))
    else:
        n = sum(1 for a in ctx.artifacts)
        print(f"\n  scanned {n} artifact(s) · scope={args.scope}\n")
        print(report.render_findings(findings, args.severity, color))
        print()
        print(report.render_scorecard(card, color))
        print()

    if args.min_score is not None and card.overall < args.min_score:
        return 2
    return report.exit_code(findings)


def cmd_fix(args) -> int:
    ctx, _ = _build_context(args)
    findings = rules.run(ctx)
    path_for = {a.label: a.path for a in ctx.artifacts if a.editable}
    plan = fixmod.plan_fixes(findings, path_for)
    if not plan:
        print("  Nothing to auto-fix. Run `scan` to see manual findings.")
        return 0
    backup_root = Path.cwd() / ".skill-doctor.bak"
    diffs, changed = fixmod.apply(plan, dry_run=args.dry_run, backup_root=backup_root)
    for d in diffs:
        print(d)
    verb = "Would fix" if args.dry_run else "Fixed"
    where = "" if args.dry_run else f" (backups in {backup_root})"
    print(f"\n  {verb} {changed} file(s){where}.")
    return 0


def cmd_rules(args) -> int:
    print("\n  skill-doctor rule catalog\n")
    for rid, sev, desc, ref in RULE_CATALOG:
        print(f"    {rid}  [{sev:<5}]  {desc}  ({ref})")
    print("\n  severity → exit code: clean=0, warn=1, error=2\n")
    return 0


def _add_common(p):
    p.add_argument("--scope", choices=["user", "project", "all"], default="all")
    p.add_argument("--path", action="append", help="extra root(s) to scan")
    p.add_argument("--skip-installed", action="store_true",
                   help="ignore installed/third-party skills")
    p.add_argument("--conventions", action="store_true",
                   help="enable opt-in MT* maintenance-convention rules")
    p.add_argument("--no-color", action="store_true")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="skill-doctor",
        description="Audit & optimize a Claude Code setup against the Skill Maintainer's Codex.")
    sub = parser.add_subparsers(dest="command")

    sp = sub.add_parser("scan", help="audit + scorecard (default)")
    _add_common(sp)
    sp.add_argument("--only", help="comma-separated rule ids to run exclusively")
    sp.add_argument("--disable", help="comma-separated rule ids to skip")
    sp.add_argument("--severity", choices=["error", "warn", "info"], default="info")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--score-only", action="store_true")
    sp.add_argument("--min-score", type=int, help="exit nonzero if overall score < N")
    sp.set_defaults(func=cmd_scan)

    fp = sub.add_parser("fix", help="apply safe auto-fixes to authored artifacts")
    _add_common(fp)
    fp.add_argument("--only", help="comma-separated rule ids")
    fp.add_argument("--disable", help="comma-separated rule ids")
    fp.add_argument("--dry-run", action="store_true", help="preview diff, write nothing")
    fp.set_defaults(func=cmd_fix)

    rp = sub.add_parser("rules", help="print the rule catalog")
    rp.set_defaults(func=cmd_rules)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        # default to scan
        args = parser.parse_args(["scan"] + (argv or []))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
