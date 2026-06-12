# Changelog

All notable changes to skill-doctor are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com); versioning is SemVer.

## [0.1.0] — 2026-06-12
### Added
- Initial release: `scan`, `fix`, and `rules` commands.
- 25 rules across skills (SK), library budget (LB), subagents (AG),
  CLAUDE.md (CM), permissions & hooks (PM), and opt-in conventions (MT),
  each mapped to a Skill Maintainer's Codex practice.
- Setup Health Score with per-category breakdown, letter grade, and a
  "biggest wins" to-do list; separate score for installed library health.
- Dry-run-by-default safe auto-fixers (whitespace, Windows paths) with backups.
- Ignore globs and configurable score weights via `.skill-doctor.toml`.
- Bundled as a Claude skill (`/skill-doctor`) and a standalone CLI.
