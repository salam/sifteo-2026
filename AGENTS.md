Please check @CLAUDINE.AGENTS.md as well, and help me organizing ongoing tasks with it.

## Task Tracking (Claudine)

- Read `.claudine/state.json` at the start of each task and identify the matching conversation by title or ID.
- Keep the board current via `.claudine/commands.jsonl`: move to `in-progress` when work starts, `in-review` when implementation is ready, and `done` after validation/acceptance.
- If the task scope changes, send a `update` command with a short concrete description of what changed.

## Commit Prep Artifacts

- Maintain `CHANGELOG.md` continuously. Every meaningful implementation should update the `Unreleased` section under `Added`, `Changed`, `Fixed`, `Docs`, or `Tests`.
- Before finalizing a commit, regenerate `.GIT_NEXT_COMMIT_MESSAGE.md` from the working tree (`git diff --name-status HEAD`, `git diff --stat HEAD`, and untracked files).
- `.GIT_NEXT_COMMIT_MESSAGE.md` should be directly usable with `git commit -F .GIT_NEXT_COMMIT_MESSAGE.md`:
  - First line: imperative summary (<=72 chars).
  - Body: grouped bullets that cover code, docs, tests, and notable assets/artifacts.
  - Final `Tests:` section listing commands run and results.

## Consistency Rules

- Do not claim a change in `CHANGELOG.md` unless corresponding file changes exist.
- Do not leave completed checklist items in `TODO.md` without matching changelog notes.
- Keep `CHANGELOG.md` project-specific (Sifteo 2026), not template text from unrelated projects.
