---
name: about-docs-folder
description: Use when looking for project documentation in the `docs` folder, or when reading, creating or working on plans in `docs/plans`.
---

# About the docs folder

## Use this skill when

- Looking for useful resources or documentation about the project in the `docs` folder.
- Reading, creating or working on plans in `docs/plans`.

## The docs folder

- `docs` (usually at the root of the project) may contain useful resources for agents when executing tasks.
- `docs/plans` contains long lasting plans with descriptions, implementation details and checklists.
  - NOTE: plans are to be considered as historical documents so don't expect them to be up to date.
  - If a plan cannot be found in `docs/plans`, then check if plans/work items exists in `AGENTS.md`.

## Plan folder structure

```
docs/plans/
├── 0-sample-plan/
│   ├── PLAN.md
│   └── QA.md
├── 1-{first plan}/
│   ├── PLAN.md
│   └── QA.md
└── 2-{second plan}/
    └── ...
```

- Each plan resides in its own folder, named `{number}-{plan name in kebab-case}`.
  - The number is incremental, so a new plan gets the highest existing number + 1.
  - The current plan is usually the plan with the highest number.
- Each plan folder contains:
  - `PLAN.md`: context for the agent, a checklist of steps (`- [ ]` / `- [x]`) and instructions for how to execute the plan.
  - `QA.md`: questions from the agent to the user. Each question gets its own `## Question {n}` heading with an `### Answer` subheading that reads `(waiting for user answer)` until the user answers.

### Sample PLAN.md

This is only a sample showing the basic parts in plans, the final structure can be determined by agents/users themselves.

```
# {title of the plan}

{context for the agent}

## Plan

- [ ] First step
- [ ] Second step
- [ ] Third step
    - [ ] Substep 1
    - [ ] Substep 2

### Execution of plan

- You should only work in the `{branch name}` branch.
- You should git commit and push regularly, particularly after making many code changes.
- After every step you should tick the step off the plan and make sure everything is committed and pushed.
- Be autonomous, but if you need my input then ask for it in [QA.md](QA.md).
```

### Sample QA.md

```
# Questions from agent to user

## Question 1

### Answer

(waiting for user answer)
```
