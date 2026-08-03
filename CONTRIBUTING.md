# Development conventions

Solo project, but a PR workflow is deliberately maintained for rigor and
as a demonstration of engineering practice (portfolio).

## Sprint → Issue → Branch → PR organization

- A **sprint** = a GitHub Milestone (`Sprint 0`, `Sprint 1`, ...),
  matching the breakdown documented in `docs/ROADMAP.md`.
- Each sprint objective = an **Issue**, attached to the Milestone.
  A sprint contains several issues (several features/objectives).
- Each issue is developed on its own **branch**, never directly on
  `main`.
- Each branch is closed by a **Pull Request** to `main`, even solo.

The sprint is thus a project management metadatum (Milestone), not
information encoded in the branch name — branches remain named after the
feature they carry, not the sprint, so they stay readable even if the
sprint breakdown is adjusted along the way.

## Branch naming

Convention: `<type>/<short-kebab-case-description>`

Types used:
- `feat/` — new feature (e.g. `feat/hierarchical-chunking`)
- `fix/` — bug fix
- `exp/` — ML experiment to compare (e.g. `exp/bge-m3-vs-e5-embeddings`)
  — specific to ML projects: one branch per tested variant, with its
  metrics in the PR, before deciding what becomes the baseline
- `docs/` — documentation only
- `chore/` — tooling, CI, dependencies
- `refactor/` — no behavior change

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) convention:
`type(scope): description in the present tense`

```
feat(chunking): add hierarchical parent-child splitting
fix(retrieval): fix RRF fusion when one of the two indexes is empty
docs(readme): update sprint 1 status
```

Enables an automatable changelog and a readable history — a genuine plus
for a recruiter browsing the git history.

## Pull requests

- One PR = one issue = one topic, deliberately small and focused.
- PR title in Conventional Commits format.
- Description: what/why (all in one section).
- Self-review before merge (checklist below); Claude Code can be used for
  automated diff review, worth mentioning as a practice in the portfolio
  README.
- **Squash merge** into `main`: one clean commit per feature in `main`'s
  history, regardless of how many intermediate commits sit on the branch.
- `main` is protected: no direct push, PR required (to be enabled in the
  repo's GitHub settings).

## Pre-merge checklist

- [ ] Tests pass (once CI is in place, Sprint 1+)
- [ ] If retrieval/generation is impacted: evaluation metrics attached to
      the PR
- [ ] No secrets/API keys committed
- [ ] `docs/ROADMAP.md` updated if sprint scope has changed

## Release tags

A lightweight tag at the close of each sprint (`sprint-0-done`, then
semver `v0.1.0` once a first end-to-end pipeline is functional) — makes
it easy to revisit the project's state at any stage for an interview
demo.
