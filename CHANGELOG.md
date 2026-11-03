# Changelog

The backend and its API contract (`docs/app-build/contracts.md`) share one version,
`major.minor.patch`, set in `src/version.py`. A change that breaks a reader raises the major, an
addition raises the minor and a fix raises the patch. Each release is tagged `v<version>` on
`main`. Work goes to `dev` first and reaches `main` when its tests pass.

## [1.0.3] - 2026-11-03

- Fix: a project's budget left out the runs that were waiting for an answer, so chats that
  paused could spend past the cap together. Every other run of the project now counts.
- Tests: the design, compare and tool loops start and resume with a scripted model.

## [1.0.2] - 2026-11-03

- geomind 0.4.15: a run's time limit also bounds model and tool calls in flight, and the run
  stops with a partial answer.

## [1.0.1] - 2026-11-03

- Fix: every design chat failed at once with "called inside its own event loop". Since
  geomind 0.4.4 the design and compare loops read the project's plants and file names on the
  event loop; the backend now reads them before the run starts.

## [1.0.0] - 2026-11-03

The first numbered release: the contract as it stood at number 52.

- Live run events over `WS /assistant/runs/{id}/stream`, with SSE as the fallback.
- `tool.finished.problem` carries a failed tool's code, such as `no_case` or `case_incomplete`
  with the missing paths.
- `POST /design/study` takes an optional `plant_version`; a study has `plant_pinned`.
- The assistant reads a project's uploaded files.
- gemini 0.5.5 and geomind 0.4.13, both from their release wheels pinned by sha256.
- `GET /system/health` has `version`.
