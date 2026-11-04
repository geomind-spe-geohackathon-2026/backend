# Backend B2: Assistant

## Goal

Chats and agent runs work through the API in `contracts.md`: a message starts a geomind run on a worker, events stream live over SSE, runs can wait for an answer, be cancelled, and be read back as a full log.

## Context

- Follow the shared rules in `../docs/phases.md` (section "Rules for every phase") and the contracts in `../docs/contracts.md`.
- Needs B1. Read `../docs/contracts.md` sections 1 (assistant), 2 (events) and 3 (geomind interfaces).
- geomind is built in parallel. Until S1 is done, write the adapters against the interfaces in the contract and test with a small stand-in that emits the contract events. When S1 is done, install `../geomind` (editable) and switch to the real `gd.Run` with `FakeLLM` in tests.

## Split of responsibilities

```
backend:  storage, access, queue, live stream                (where and who)
geomind:  understanding, choosing the loop, tools, memory     (what and how)
```

The backend never picks a loop or an agent.

## Layout

```
src/api/v1/assistant/
├── chat/    router.py  schemas.py  services.py
└── runs/    router.py  schemas.py  services.py  jobs.py
    └── adapters/  llm.py  store.py  workspace.py  events.py  hooks.py
src/core/clients/postgres/models/        chat.py  run.py
src/core/clients/postgres/repositories/  chat.py  run.py
src/core/clients/redis/                  pubsub for run events
```

## Steps

1. **Models:** `Chat`, `Message`, `Run`, `RunEvent` (the stored events, in order; geomind recovers and resumes from them, no checkpoints). Usage totals on `Run`. Migration.
2. **chat:** routes from the contract. Posting a message stores it, creates a `queued` run, enqueues `runs.jobs.execute_run`, returns both.
3. **adapters:**
   - `llm.py`: the `LLM` interface over `core/clients/openrouter`.
   - `store.py`: the `RunStore` interface over the run repositories.
   - `workspace.py`: the `Workspace` interface: `plant()` through `core/gemini`, `documents()` through the document store (empty until documents exist).
   - `events.py`: a geomind callback that stores each event and publishes it to Redis.
   - `hooks.py`: token budget per project, approval for heavy tools, project access.
4. **jobs.py:** `execute_run` builds `gd.Run` with the adapters and starts or resumes it; marks the run `failed` with the error on exceptions.
5. **runs routes:** get, SSE events (replay from `Last-Event-ID`, then live from Redis), log, answer (resumes the run from its stored events), cancel.
6. **Tests:** the full flow with `FakeLLM`: message → events in order → `done`; a request → `waiting` → answer → `done`; cancel; reconnect with `Last-Event-ID`.

## Done when

- The flow above passes in tests and by hand with `curl`.
- `GET /runs/{id}/log` returns every prompt, answer, tool call and token count.
- Import boundary tests pass.

## Report back

What was built, any contract change needed, and anything geomind or the frontend should know.

## Notes for the rewrite (contracts v13, geomind interfaces 2.4)

- `save_event` stores the full `event.to_dict()`; events are rebuilt with `gd.event_from_dict`.
- Delegated runs write into the root run's log (root `run_id`, own `agent` and `parent`); `load_events(root)` returns all.
- `text.delta` is streamed but not saved by geomind; SSE replay of text after a reconnect comes from a short-lived Redis buffer.
- No checkpoints (interfaces 2.3).
- Accepted (contracts v14, interfaces 2.5): public `step.finished` is `{index, usage, text}` (the step's full assistant text). The Redis text buffer only covers the step still running; finished steps replay from stored `step.finished`.
- Contracts v16 (interfaces 2.6): event `sequence` numbers can have gaps (never assume contiguous; replay uses `sequence > Last-Event-ID`); `save_state` data carries a `compaction` key, stored unchanged; the backend never passes `gd.Run(agent=...)` (manual testing only).
