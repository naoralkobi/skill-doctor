# Changelog

All notable changes to skill-doctor are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com); versioning is SemVer.

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
