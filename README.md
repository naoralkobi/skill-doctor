# skill-doctor

**Audit, score, and optimize your Claude Code setup against best practices.**

Engineers accumulate skills, install third-party skills, write `CLAUDE.md` files,
add hooks, and grant permissions — with no way to know what has drifted from good
practice. `skill-doctor` scans all of it, reports findings mapped to a documented
guide, gives your setup a **health score**, and applies safe auto-fixes.

It is both a **standalone CLI** and a **Claude skill** (`/skill-doctor`). It is
read-only by default and never touches installed/third-party skills.

> 📖 **Read the guide:** [The Skill Maintainer's Codex](https://naoralkobi.github.io/skill-doctor/)
> — the 27-practice reference this tool enforces (and scores **A** against itself).

---

## Why

- **One number, not a wall of text.** A Setup Health Score (0–100 + letter grade)
  per category, with a "biggest wins" to-do list.
- **Honest separation.** Your authored setup is scored separately from the
  installed third-party library, so you're never penalized for other people's skills.
- **Safe by default.** `scan` writes nothing. `fix` only ever edits *your*
  artifacts, with backups and a dry-run diff.
- **Zero dependencies.** Pure Python 3 standard library.
- **Traceable.** Every finding links to a specific practice in the guide.

---

## Install

Requires **Python 3.11+** (uses stdlib `tomllib`). No packages to install.

```bash
git clone https://github.com/naoralkobi/skill-doctor.git
cd skill-doctor
python3 scripts/skill_doctor.py scan
```

Optional — a short alias:

```bash
alias skill-doctor='python3 ~/skill-doctor/scripts/skill_doctor.py'
```

### Use it as a Claude skill

Symlink the project into your skills directory so Claude can run it in-session as
`/skill-doctor`:

```bash
ln -s ~/skill-doctor ~/.claude/skills/skill-doctor
```

(Symlinking keeps the repo as the single source of truth — Codex Practice 18.)

---

## Usage

```bash
skill-doctor scan      # audit + scorecard (default; writes nothing)
skill-doctor fix       # apply safe auto-fixes to your artifacts
skill-doctor rules     # print the rule catalog
```

### `scan`

```bash
skill-doctor scan                       # everything, all scopes
skill-doctor scan --scope user          # only ~/.claude
skill-doctor scan --skip-installed      # ignore third-party skills
skill-doctor scan --score-only          # just the scorecard
skill-doctor scan --json                # machine-readable
skill-doctor scan --conventions         # also check opt-in MT* conventions
skill-doctor scan --min-score 80        # exit nonzero if score < 80 (CI gate)
skill-doctor scan --only SK002,SK007    # run specific rules
skill-doctor scan --disable SK011       # skip specific rules
skill-doctor scan --severity warn       # hide info-level findings
```

Example output:

```
  scanned 9 artifact(s) · scope=all

  my-skill
    ✗ SK002 Missing `description` in frontmatter. Part I·03
    ▲ SK006 SKILL.md body is 642 lines (keep <500). Part I·01

  Setup Health  ███████████░░░  78 / 100   (B)
    Skills authoring ........  72  (C)   ← 1 error, 1 warn
    CLAUDE.md / config ...... 100  (A)
    Subagents ............... 100  (A)
    Permissions & hooks .....  80  (B)
  Biggest wins:
    +15 SK002 Missing description — my-skill   (Part I·03)  [manual]
    +5  SK010 Windows path — deploy-skill      (Part I·10)  [auto]
  Installed library health: 64 / 100 (D) — 12 bloated description(s)
```

### `fix`

```bash
skill-doctor fix --dry-run    # preview a unified diff, write nothing
skill-doctor fix              # apply (backups in ./.skill-doctor.bak/)
```

Auto-fixable rules: `SK010` (Windows → forward-slash paths) and `SK012`
(trailing whitespace / final newline). Everything else is reported with a
suggestion for you to decide.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | clean (no warnings or errors) |
| 1 | warnings present |
| 2 | errors present, or score below `--min-score` |

Use `--min-score` in CI to fail a PR when a skill regresses.

---

## What it scans

| Artifact | Location(s) | Editable by `fix` |
|----------|-------------|-------------------|
| Authored skills | `~/.claude/skills/*/SKILL.md`, `./.claude/skills/*/SKILL.md` | ✅ |
| Installed skills | `~/.claude/plugins/cache/**`, `…/marketplaces/**` | ❌ audit-only |
| Subagents | `~/.claude/agents/*.md`, `./.claude/agents/*.md` | ✅ |
| CLAUDE.md / rules | `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules/*.md` | ✅ |
| Permissions & hooks | `settings.json`, `settings.local.json` | ❌ advisory |

---

## Rules & scoring

25 rules across six families, each mapped to a practice in the guide:
`SK` skills · `LB` library budget · `AG` subagents · `CM` CLAUDE.md ·
`PM` permissions/hooks · `MT` opt-in conventions.

Scoring is deterministic: each category starts at 100 and deducts **−15** per
error, **−5** per warn, **−1** per info (clamped 0–100). Overall is a weighted
mean (skills weighted highest). Grades: A ≥90, B ≥80, C ≥70, D ≥60, F <60.

See the full catalog in **[reference/rules.md](reference/rules.md)** or run
`skill-doctor rules`.

---

## Configuration

Optional `.skill-doctor.toml` in your working directory:

```toml
ignore = ["tests/**", "**/.skill-doctor.bak/**"]

[rules]
disable = ["SK011"]

[score]
error = 15
warn = 5
info = 1
budget_chars = 15500
```

---

## The guide

The **Skill Maintainer's Codex** is a self-contained, 27-practice reference
covering the full lifecycle: Author → Extend → Configure → Maintain → Distribute.
Every `skill-doctor` finding cites a practice from it (e.g. `Part I·03`).

- 🌐 Live: **https://naoralkobi.github.io/skill-doctor/**
- 📄 Source: [`docs/index.html`](docs/index.html)

---

## Project layout

```
skill-doctor/
├── SKILL.md                # Claude skill entry point
├── README.md
├── CHANGELOG.md
├── .skill-doctor.toml      # default config
├── scripts/                # the engine (stdlib only)
│   ├── skill_doctor.py     # CLI: scan | fix | rules
│   ├── discovery.py        # artifact discovery
│   ├── parse.py            # frontmatter / json / toml / links
│   ├── rules.py            # rule registry
│   ├── report.py           # reporting + scoring
│   └── fix.py              # safe auto-fixers
├── reference/rules.md      # full rule catalog
├── tests/                  # pytest eval suite (incl. self-compliance)
└── docs/                   # the Skill Maintainer's Codex (HTML)
```

## Development

```bash
python3 -m pytest tests/        # run the eval suite
python3 scripts/skill_doctor.py scan --path . --skip-installed   # self-audit → A
```

`skill-doctor` dogfoods the guide it enforces: concise SKILL.md with detail in
`reference/`, third-person trigger-rich description, a tests-as-evals suite,
documented scoring weights, read-only-by-default least privilege, and a
`test_self_compliance` test that fails if the tool can't grade itself an **A**.

## License

MIT © naoralkobi
