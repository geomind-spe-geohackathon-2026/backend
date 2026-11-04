# Changelog

The backend and its API contract (`docs/app-build/contracts.md`) share one version,
`major.minor.patch`, set in `src/version.py`, the same scheme as the frontend. For now every
release stays on 1.1 and raises only the patch: 1.1.0, 1.1.1 and on (Sahand, 2026-11-03). Each
release is tagged `v<version>` on `main`. Work goes to `dev` first and reaches `main` when its
tests pass.

## Unreleased

- `GET /assistant/runs/{id}/agents`: one row per agent session of a run, running or finished,
  with its model, status, steps, LLM calls, tokens (cached included), cost, tool calls (name,
  outcome, time; no inputs or outputs) and its context used, peak, window and left against its
  own model's window. Context is per session, never summed over the run; the run total counts
  each LLM call once and equals `runlog`'s `run.usage`. geomind's own per-session figures
  (0.4.24: `step.started.session` / `context_window`, `step.finished.context`, the root
  `run.finished.sessions` / `total`) are used where the log has them; older logs are counted
  from their LLM calls.
- `step.started.context_window` is the window of that step's model, as geomind looks it up, not
  the single `GEOMIND_CONTEXT_WINDOW` (still the fallback); geomind's own value passes through.

## [1.1.10] - 2026-11-04

- Connector Check works again: the backend gives geomind's MCP client its `gd.mcp.Server` record,
  not a plain dict, so a check no longer fails with "'dict' object has no attribute 'name'". Runs
  get the project's connectors as `gd.mcp.Server` records too; with dicts, a run with a connector
  failed as soon as geomind loaded the servers.
- Check is a health check: one round trip through geomind's MCP client, answered with `steps`
  (`reachable`, `initialize`, `auth`, `tools`, each `ok`, `failed` or `skipped` with a readable
  reason, never a header value or a program error), `server_info` (null: geomind 0.4.23 does not
  hand out the `initialize` answer) and `elapsed_ms`. The fields are additive; `status`, `error`
  (`"<code>: <reason>"`) and `tools` stay as they were.
- A case gemini accepts in a chat (`set_case`, a saved profile) and a plant `build_plant` stores
  are saved as the project's next case or plant version, with the run's author, so the Case and
  Plant pages show them. Content equal to the latest version saves nothing.
- `ASSISTANT_RUN_MAX_TOKENS` defaults to 10,000,000 tokens per run (was 2,000,000).

## [1.1.9] - 2026-11-04

- geomind 0.4.23. The workspace gives each project its memory (or none when the project has it
  off), so the model check asks for the `store` memory settings: `GEOMIND_MEMORY=on` needs only
  `GEOMIND_MEMORY_SIMILARITY`, never `GEOMIND_MEMORY_DIR`. The examples set `GEOMIND_MEMORY=on`.

## [1.1.8] - 2026-11-04

- gemini 0.6.3 (additions only).

## [1.1.7] - 2026-11-04

- geomind 0.4.22 and gemini 0.6.2, pinned by URL and sha256. geomind takes one model per role
  (`GEOMIND_<ROLE>_MODEL`, 17 roles), and needs `GEOMIND_MAX_STEPS`, `GEOMIND_MAX_OUTPUT_TOKENS`,
  `GEOMIND_DESIGN_CONCURRENCY`, `GEOMIND_ENGINEER_MAX_STEPS` and `GEOMIND_EVOLVE_*`; the examples set
  them and `GEOMIND_PROVIDER=deepseek`. `GEOMIND_MEMORY=off` for now: with `on`, geomind 0.4.22
  wants a memory folder and would use it for every project that has no memory of its own.
- geomind reads the case, the Knowledge list and a run's events on the event loop; the workspace
  and the store now read them before the run and keep them current.
- gemini 0.6 adds the study method `evolve`; `GET /plant/flowsheet/suggest` works.
- A question with options also takes the user's own typed answer (geomind 0.4.22 marks it as
  typed); only the step-limit question still takes only `continue` or `stop`. Answers that were
  accepted before are accepted as before.

## [1.1.6] - 2026-11-03

- Next-step suggestions (Sahand): an assistant answer keeps the steps geomind suggests with it
  (`message.suggestions`, migration 0014); `GET /assistant/suggestions` and an empty chat's state
  give them for a chat that has no message yet. They follow the whole project's state, which
  the workspace gives geomind as `project_state`.
- `ASSISTANT_MODEL_PREFIX` takes several prefixes, comma separated.

## [1.1.5] - 2026-11-03

- `step.started` carries `context_window`, so the chat can show how full a call's context is.
- `POST /plant/flowsheet/validate` adds `warnings`; new `GET /plant/flowsheet/suggest` lists the
  ports a port may connect to (gemini 0.6).
- geomind after 0.4.21 takes no sandbox; the backend passes one only to a geomind that does.
- Tests: the socket test for a client that leaves no longer depends on timing.

## [1.1.4] - 2026-11-03

Names in the API and code follow what they are (Sahand): documents are `rag`, connectors are
`mcp`. People still see Library, Knowledge and Connectors in the app.

- `/workspace/documents` is `/workspace/rag`, `/workspace/connectors` is `/workspace/mcp`, the
  project's `connectors` is `mcp`; codes `rag_document_not_found`, `mcp_server_not_found`.
- New: `GET /workspace/rag/{id}/file` shows a file inline, and `GET /workspace/rag/{id}/text`
  gives the text the agents search.
- The workspace offers geomind's new names `rag` and `mcp` beside `documents` and `connectors`.
- Migration 0013 renames the tables `rag_documents` and `mcp_servers` and `projects.mcp`.
- The command-line scripts moved from `src/scripts/` to the root `scripts/`: run them from the
  backend folder as `python -m scripts.projects` and `python -m scripts.knowledge`.

## [1.1.3] - 2026-11-03

Knowledge is RAG, Connectors are MCP, and neither is the agents' memory (Sahand).

- Knowledge is a shared document base: `/workspace/documents` without `project` lists, adds
  and deletes shared documents (only an admin writes). The agents search it through
  `Workspace.knowledge_search` (passages with document and page), `knowledge_files` and
  `knowledge_file`. A PDF keeps its pages. `python -m scripts.knowledge add` seeds a file.
- The knowledge-entry routes of 1.1.2 are gone. The agents' memory holds only what geomind
  writes, kept as given; the app shows only the project's on/off switch.
- Migration 0012: documents may have no project; the memory table is `memory_entries`.
- geomind 0.4.21: a project's attached files are found by `search_documents`, and fixes from the
  third and fourth live runs.

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
