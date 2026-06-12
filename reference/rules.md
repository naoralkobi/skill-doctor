# skill-doctor rule catalog

## Contents
- Severity & scoring
- Skills (SK)
- Library budget (LB)
- Subagents (AG)
- CLAUDE.md / config (CM)
- Permissions & hooks (PM)
- Maintain conventions (MT, opt-in)

Each rule maps to a practice in the **Skill Maintainer's Codex** (the `docs/`
guide). Severity drives both the report and the score.

## Severity & scoring
| Severity | Meaning | Points deducted | Exit code |
|----------|---------|-----------------|-----------|
| error    | breaks the spec / a link | −15 | 2 |
| warn     | quality / budget risk | −5 | 1 |
| info     | nice-to-have / note | −1 | 0 |

Each scored category starts at 100, deducts per finding, and is clamped to
0–100. Overall = weighted mean (skills weighted highest). Your authored setup
and the installed third-party library are scored **separately** so you are never
penalized for other people's skills.

## Skills (SK)
| ID | Sev | Checks | Guide | Auto-fix |
|----|-----|--------|-------|----------|
| SK001 | error/warn | `name` present, `^[a-z0-9-]{1,64}$`, no reserved words (`anthropic`,`claude`) | I·04 | – |
| SK002 | error | `description` present and ≤1024 chars | I·03 | – |
| SK003 | warn | description in third person (no "I/You/We can…") | I·03 | – |
| SK004 | warn | description not vague; has an explicit "Use when…" trigger | I·03 | – |
| SK005 | warn | description within metadata budget (trim toward ~150) | Interlude | – |
| SK006 | warn | SKILL.md body under 500 lines | I·01 | – |
| SK007 | error | internal reference links resolve | I·05 | – |
| SK008 | warn | references kept one level deep from SKILL.md | I·05 | – |
| SK009 | info | reference files >100 lines have a Contents section | I·05 | – |
| SK010 | warn | no Windows-style backslash paths | I·10 | ✓ |
| SK011 | info | no time-sensitive phrasing ("before 2025…") | I·09 | – |
| SK012 | info | no trailing whitespace; file ends with newline | I·01 | ✓ |

## Library budget (LB)
| ID | Sev | Checks | Guide |
|----|-----|--------|-------|
| LB001 | warn/info | total skill metadata within the ~15.5k char budget | Interlude |

## Subagents (AG)
| ID | Sev | Checks | Guide |
|----|-----|--------|-------|
| AG001 | error | subagent has `name` + `description` | II·12 |
| AG002 | info | subagent declares `tools` (least privilege) | II·12 |
| AG003 | warn | description rich enough for reliable delegation | II·12 |

## CLAUDE.md / config (CM)
| ID | Sev | Checks | Guide |
|----|-----|--------|-------|
| CM001 | warn | CLAUDE.md under 200 lines | III·15 |
| CM002 | warn | `@imports` resolve | III·15 |
| CM003 | info | very long files split into `.claude/rules/` | III·15 |

## Permissions & hooks (PM)
| ID | Sev | Checks | Guide |
|----|-----|--------|-------|
| PM001 | info | permissions allow/deny/ask summary (not scored) | III·17 |
| PM002 | warn | no over-broad allow rules (`Bash(*)`, `curl *`) | IV·22 |
| PM003 | info | hooks summary; flag missing matchers | II·14 |

## Maintain conventions (MT, opt-in via `--conventions`)
These are team conventions, **not** part of the official spec.
| ID | Sev | Checks | Guide |
|----|-----|--------|-------|
| MT001 | info | a version is recorded | IV·19 |
| MT002 | info | a CHANGELOG sits beside the skill | IV·20 |
| MT003 | info | an owner/author is recorded | IV·23 |
