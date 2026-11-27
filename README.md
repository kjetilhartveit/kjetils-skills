# kjetils-skills

Kjetil's public agent skills, in [skills/](skills/): visual explainers (`explain-visually` and the `explain-with-*`
skills), the shared `explainer-kit`, and `merge-renovate-pull-requests`.

## Install

- **Claude Code, Codex and other agents:** `npx skills add https://github.com/kjetilhartveit/kjetils-skills.git -g`
- **claude.ai:** the repo is also a plugin marketplace. Customize > Plugins > Add > Add marketplace, enter
  `kjetilhartveit/kjetils-skills` and install the plugin `kjetils-skills`.
- **Claude Code as a plugin:** `/plugin marketplace add kjetilhartveit/kjetils-skills`, then
  `/plugin install kjetils-skills@kjetils-skills`.

The plugin picks up every `skills/<name>/SKILL.md` by itself. `plugin.json` has no `version`, so each commit is a new
version. If you installed the skills with `npx skills` and also added the plugin in claude.ai, turn off the copy
claude.ai syncs into Claude Code with `claude plugin disable kjetils-skills@synced`, so the skills don't load twice.
