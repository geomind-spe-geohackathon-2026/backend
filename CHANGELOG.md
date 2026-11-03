# Changelog

The backend and its API contract (`docs/app-build/contracts.md`) share one version,
`major.minor.patch`, set in `src/version.py`, the same scheme as the frontend. For now every
release stays on 1.1 and raises only the patch: 1.1.0, 1.1.1 and on (Sahand, 2026-11-03). Each
release is tagged `v<version>` on `main`. Work goes to `dev` first and reaches `main` when its
tests pass.

## [1.1.3] - 2026-11-03

Knowledge is RAG, Connectors are MCP, and neither is the agents' memory (Sahand).

- Knowledge is a shared document base: `/workspace/documents` without `project` lists, adds
  and deletes shared documents (only an admin writes). The agents search it through
  `Workspace.knowledge_search` (passages with document and page), `knowledge_files` and
  `knowledge_file`. A PDF keeps its pages. `python -m src.scripts.knowledge add` seeds a file.
- The knowledge-entry routes of 1.1.2 are gone. The agents' memory holds only what geomind
  writes, kept as given; the app shows only the project's on/off switch.
- Migration 0012: documents may have no project; the memory table is `memory_entries`.

## [1.1.2] - 2026-11-03

- Knowledge: geomind's shared memory as `/workspace/knowledge`, with list, search, read, add,
  change, delete and CSV import; entries are checked by geomind's own rule.
- Connectors: MCP servers as `/workspace/connectors`, secrets sealed at rest and never sent back,
  checked through geomind's MCP client.
- A project chooses `memory` (on or off) and its `connectors`; runs get them through the
  workspace (`memory`, `connectors`), as agreed with geomind.
- Migration 0011.
- gemini 0.5.14 (backward compatible; multi-plant studies run their plants in parallel), sandbox
  image `gemini-sandbox:0.5.14`.

## [1.1.1] - 2026-11-03

- gemini 0.5.10 and geomind 0.4.19, from their release wheels pinned by sha256; the sandbox
  image is `gemini-sandbox:0.5.10`.
- `GEOMIND_RETRY_COUNT` and `GEOMIND_RETRY_DELAY` are required for live runs; the examples set
  5 retries, 2 seconds apart. The app stops at startup when either is missing.
- New tool error codes in `tool.finished.problem`: `context_exceeded`, `already_read`.

## [1.1.0] - 2026-11-03

- Versions follow the frontend's scheme: 1.1, then only the patch goes up.
- Tests: a run cancelled before it starts ends as cancelled.

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
