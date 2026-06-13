# Changelog

All notable changes to skill-doctor are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com); versioning is SemVer.

## [0.2.1] — 2026-06-13
### Fixed
- When installed into `~/.claude/skills`, the tool no longer audits its own
  bundled `tests/fixtures` as if they were real skills (default ignore globs).
- Dedupe discovered artifacts by resolved path, so settings/CLAUDE.md/agents
  aren't double-reported when user and project scopes resolve to the same file.

## [0.2.0] — 2026-06-13
### Changed
- Skill-only: removed the standalone-CLI install/usage/positioning. The bundled
  Python engine is now run by the `/skill-doctor` skill inside a Claude session,
  not installed or invoked by hand. README and SKILL.md reframed accordingly.

## [0.1.1] — 2026-06-12
### Fixed
- Dedupe installed skills that appear in both `plugins/cache` and
  `plugins/marketplaces` so they're audited and scored once.
- Link checking (SK007/008) now only follows real markdown links and strips
  fenced code blocks, eliminating false "broken link" findings from URLs,
  absolute paths, and example snippets.
### Changed
- Text report hides info-level notes for read-only installed skills (still
  counted in the score and `--json`).

### Added — GitHub Pages
- `docs/index.html` serves the Skill Maintainer's Codex as the repo's Pages site.

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
