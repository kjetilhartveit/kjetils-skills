---
name: split-large-files
description: Use when creating or editing a file that agents read often (a skill's SKILL.md, AGENTS.md, CLAUDE.md, instructions, docs agents are pointed to) and it is or becomes large (about 300 lines or 20 KB), or when asked to find or split large files to save tokens and context.
---

# Split large files

Agents pay for every line they read. A skill's `SKILL.md` and an `AGENTS.md` are read in full, often in every chat
where they apply, so a long one fills the context with sections the agent doesn't need. Splitting such a file into a
short core and topic files read on demand (progressive disclosure) keeps the cost where it's earned.

## Use this skill when

- You create or edit a `SKILL.md`, `AGENTS.md`, `CLAUDE.md` or another file agents are told to read, and it's above the
  thresholds below, or your change takes it there.
- Asked to find large files, cut token usage or tidy a skill repo.
- A skill or instruction file has grown sections that only some of its readers need.

Not for files agents rarely read: archives, logs, plans that are done, generated files, lockfiles, data. Their size
costs nothing until someone reads them, and then the agent reads only the part it needs. Leave them alone.

## Thresholds

| File                                                    | Split when above          | Why                                      |
| ------------------------------------------------------- | ------------------------- | ---------------------------------------- |
| `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, instruction files | 300 lines or 20 KB        | Read whole, every time they apply        |
| Reference files inside a skill                          | 500 lines or 40 KB        | Read on demand, but whole                |
| Code                                                    | Only with a reason (below) | Agents read code in parts and search it |

These are where to look, not hard limits: a 350-line skill that every reader needs in full is fine. Anthropic's own
guidance for skills is to keep `SKILL.md` under 500 lines; we aim lower because several of our skills load in the same
chat.

Code files are split for the code's sake (separate concerns, a module that's hard to navigate), not for tokens. Follow
the repo's coding conventions; this skill only adds that a code file above about 1000 lines is worth
a look when you're already changing it.

## Find them

```bash
python <this skill's folder>/scripts/find_large_files.py <repo or folder> [more folders]
```

It lists the agent-facing files above the thresholds, largest first, and the reference files inside a skill that its
`SKILL.md` never mentions. `--all` adds every other text file above 1000 lines or 80 KB, `--json` gives the result as
JSON. It skips `.git`, `node_modules`, lockfiles, build folders and folders named `archive`. Exit code 1 means it found
something, so it works as a check in a doctor script or CI.

## How to split a skill

1. **Read the whole file and sort its sections** by who needs them: every reader (the core), or only readers doing one
   kind of work (a topic).
2. **Keep the core in `SKILL.md`:** the frontmatter, "Use this skill when", rules that always apply, and a short map of
   the topic files saying when to read each one: "If you're setting up OneDrive on Linux, read
   [references/onedrive-linux.md](references/onedrive-linux.md)." The map is what makes the split work; a topic the
   agent doesn't know exists is a topic it won't read.
3. **Move each topic to `references/<topic>.md`**, one level deep. Topic files link back to `SKILL.md` if they need to,
   but not to each other, so an agent never has to chase a chain of files.
4. **Move, don't rewrite.** Keep the wording, so the diff shows a move and the review stays small. Tighten later, in its
   own commit.
5. **Check other places that point into the file**, such as another skill linking to a section anchor
   (`other-skill/SKILL.md#some-section`), and update them: `grep -rn "<skill name>" <your skill repos>`.
6. **Commit the split on its own**, e.g. `refactor(<skill>): move <topics> to references`.

The same goes for `AGENTS.md`: keep what every agent in the repo needs, and move the rest to skills or docs that the
`AGENTS.md` points to with an "If …, read …" line.

## Verify the split

- Run `find_large_files.py` again: the file is under the threshold and no reference file is unmentioned.
- Compare the words before and after: `git diff --stat` shows lines moved, not lost. For a check of the text itself,
  `git diff -M --color-moved=zebra` marks moved lines differently from changed ones.
- Read the new `SKILL.md` as an agent would on a typical task, and check that the map sends you to the right topic file,
  and that you're not sent to one for most tasks. If most readers need a topic, it belongs in the core.
- If the file is a skill other agents run (an autonomous run, a scheduled one), it's worth one run of a typical task with
  the split skill before you rely on it.
