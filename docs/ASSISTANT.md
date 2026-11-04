# Assistant (chat, runs, usage)

Routes follow `../../docs/contracts.md`. Only `runs/adapters/` imports geomind.

## Flow

1. `POST /assistant/chat/{id}/messages` adds the user message and a `queued` run
   (one active run per chat, else `409 conflict`), then sends `assistant.runs.start`
   by name. A down queue marks the run `failed` and answers `503 unavailable`.
2. The worker claims the run (`queued` to `running`), opens its own DB, Redis and MinIO
   connections and runs `gd.Run.astart()`. The geomind run id is `run.id.hex`.
3. Events: geomind saves each event (`run_events`, full `to_dict()`), then tells the
   callbacks in order: `RunRecorder` updates the row (loop, usage, `waiting` with the
   request, the end with `error = {code: stop_reason, message}`), then `EventPublisher`
   publishes public events to Redis. `text.delta` is not stored; it is buffered in
   Redis (`run_delta:*`, TTL `ASSISTANT_DELTA_TTL_SECONDS`) until `step.finished`.
4. `GET .../events` replays stored public events after `Last-Event-ID`, adds the buffered
   text of running steps, once per step and after the stored events, as one `text.delta`
   without id and with `buffered: true` (the client replaces the step's text with it),
   then streams live. It ends after
   the root run's `run.finished` (delegated runs also emit one).
5. `POST .../answer` validates against the stored request, moves `waiting` to `running`
   atomically and sends `assistant.runs.resume`. `POST .../cancel` sets the Redis flag
   read by geomind's `Cancellation` hook; a waiting run is resumed once with a stand-in
   answer and ends `cancelled`.
6. A crash outside geomind stores and publishes a `run.finished` (`failed`) so streams end.

## Store and workspace

`DatabaseRunStore` is sync and runs DB work on the worker loop through `LoopBridge`.
geomind's `engine.resume` reads `load_events` on the loop itself, so `adapters.resume`
warms the store first. Artifacts are rows in `run_artifacts` with both ids;
`save_chat_artifact` / `load_chat_artifact` read the newest row per chat. The workspace
copies a case's MinIO files into a per-run temp folder; documents use
`src/core/rag`.

## Settings

`ASSISTANT_LLM` (`openrouter` or `fake`, fake refused in production),
`ASSISTANT_SANDBOX` (`none` or `docker`; `docker` starts geomind's `run_python` sandbox containers from the worker through the host socket, image and limits in `GEOMIND_SANDBOX_IMAGE`, `_TIMEOUT`, `_MEMORY`, `_DISK`, `_CPU`; `DOCKER_GID` is the host's docker group for the worker container), `GEOMIND_SEARCH_URL` (SearXNG for `web_search`, `http://searxng:8080` in production; empty means the web tools are not offered), , `ASSISTANT_RUN_MAX_TOKENS` (per run),
`ASSISTANT_DELTA_TTL_SECONDS`.
