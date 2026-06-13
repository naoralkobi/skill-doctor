# skill-doctor

**Audit, score, and optimize your Claude Code setup against best practices.**

Engineers accumulate skills, install third-party skills, write `CLAUDE.md` files,
add hooks, and grant permissions — with no way to know what has drifted from good
practice. `skill-doctor` scans all of it, reports findings mapped to a documented
guide, gives your setup a **health score**, and applies safe auto-fixes.

It runs entirely **inside a Claude Code session**: invoke **`/skill-doctor`** (or
just ask Claude to audit your skills) and Claude runs the bundled engine for you.
It is read-only by default and never touches installed/third-party skills.

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

`skill-doctor` is a Claude Code skill. Put it where Claude discovers skills:

```bash
git clone https://github.com/naoralkobi/skill-doctor.git
ln -s "$PWD/skill-doctor" ~/.claude/skills/skill-doctor
```

Then restart Claude Code (or run `/reload-plugins`). The bundled engine needs
**Python 3.11+** (stdlib only — nothing to `pip install`). Symlinking keeps the
repo as the single source of truth — Codex Practice 18.

---

## Using it in a session

Invoke the skill and let Claude drive it:

```
/skill-doctor
```

Or just ask in natural language — *"audit my skills"*, *"score my Claude setup"*,
*"fix the easy issues"* — and Claude triggers the skill from its description.

Claude runs the bundled engine and walks you through the results:

1. **Audit + score** — scans your setup and shows the findings + Setup Health scorecard.
2. **Biggest wins** — an ordered list of what costs the most points.
3. **Preview fixes** — a diff of the safe auto-fixes, before anything is written.
4. **Apply** — on your go-ahead, applies them (backups kept) and re-scores.

You can scope the request — *"only my own skills"*, *"just the score"*, *"check
the DogWalker project"* — and Claude passes the right options through.

Example of what Claude shows you:

```
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

Auto-fixable rules: `SK010` (Windows → forward-slash paths) and `SK012`
(trailing whitespace / final newline). Everything else is reported with a
suggestion for you to decide.

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
├── scripts/                # the engine the skill runs (stdlib only)
│   ├── skill_doctor.py     # engine entry point (scan / fix / rules)
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

For contributors working on the engine (end users never run these — Claude does):

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
