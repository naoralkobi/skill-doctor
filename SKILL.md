---
name: skill-doctor
description: Audits and optimizes a Claude Code setup — skills, CLAUDE.md, subagents, permissions, and hooks — against best practices, and scores its health. Use when reviewing, linting, auditing, or improving local skills, or before publishing a skill.
version: 0.1.0
metadata:
  author: naoralkobi
  homepage: https://github.com/naoralkobi/skill-doctor
---

# skill-doctor

Audit a Claude Code setup against the Skill Maintainer's Codex, get a health
score, and apply safe auto-fixes. Read-only by default.

## Quick start

```bash
python scripts/skill_doctor.py scan          # audit everything + scorecard
```

Scope it, or score only:

```bash
python scripts/skill_doctor.py scan --scope user --score-only
python scripts/skill_doctor.py scan --skip-installed     # only your own skills
```

## Workflow

Copy this checklist and check off each step:

- [ ] Step 1: `scan` — read the findings and the Setup Health scorecard
- [ ] Step 2: review the "Biggest wins" list (ordered by points lost)
- [ ] Step 3: `fix --dry-run` — preview the unified diff of safe fixes
- [ ] Step 4: `fix` — apply (backups land in `.skill-doctor.bak/`)
- [ ] Step 5: re-run `scan` to confirm the score improved

## Commands

- `scan` — audit + scorecard (default; writes nothing). Flags: `--scope`,
  `--skip-installed`, `--conventions`, `--only`/`--disable`, `--severity`,
  `--json`, `--score-only`, `--min-score N`.
- `fix` — apply only auto-fixable rules to **your** artifacts. `--dry-run` previews.
- `rules` — print the rule catalog.

## Reference

- Full rule catalog and guide mapping → [reference/rules.md](reference/rules.md)

## Rules

- ALWAYS run `fix --dry-run` before `fix`.
- NEVER edit installed/third-party skills; `fix` only touches authored artifacts.
