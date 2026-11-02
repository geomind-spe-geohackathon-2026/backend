# geomind inventory (A3)

Snapshot: /Users/sahand/Desktop/geomind-spe-geohackathon-2026/backend/.tmp/snap/geomind-origin (origin main, eeb80d9).
Sources: .claude/docs/{contracts,api,events,plan,hooks,providers,testing,context}.md; geomind/ source; tests/unit/snapshots/api.json (version 0.2.0).
gd.__version__ = "0.2.0" (0.2.0 is unreleased; CHANGELOG.md). .claude/docs/contracts.md: file version 15, interface version 2.5.
The shared contract (geomind-spe-geohackathon-2026/docs/contracts.md) is file version 19, interface 2.6; geomind's copy is behind it.

## Differences from section 5.4 of the build prompt

Re-evaluated against app-frontend-backend.md sections 5.2 and 5.4 (the snapshot's code and docs win where they differ from the prompt).

1. RunResult has no `message` (fields: run_id, status, answer, request, usage, steps, stop_reason). `run.error.message` comes from the `run.finished` event (`RunFinished.message`, streamed and stored).
2. Run.load also takes `sandbox` and `permissions`; pass them again with llm, store, workspace, callbacks and hooks.
3. The RunStore has 7 methods. `save_chat_artifact` / `load_chat_artifact` do NOT exist in geomind (not in api.json, not tested by check_run_store). The shared contract (section 2.6) and 5.4 say they are decided. Backend implements them additively and reports "geomind: chat-scoped artifact methods not released yet".
4. Workspace.case(project_id) EXISTS, as 5.4 requires. The earlier note that it did not was wrong. Returns `(case dict, folder)` or `None`.
5. `start()` and `resume()` raise RunError inside a running event loop; use `astart()` and `aresume()` there.
6. `astart()` routes first unless `agent=` or `loop` is set: a nested Coordinator run (one LLM call, logged, counted in usage, coordinator_model default claude-haiku-5.5) picks the loop and agent. 5.4 does not mention this call.
7. OpenRouter(api_key, base_url, transport) has no model or settings argument. It reads OPENROUTER_API_KEY and raises ProviderError without one; `Run(llm=None)` builds OpenRouter() at construction, so `Run(...)` without llm fails with no key. Model comes from runtime settings (default anthropic/claude-sonnet-5.5, env GEOMIND_MODEL), not per project.
8. TokenBudget and CostBudget count the run tree: this run plus every run above it, nested runs included, but not a sibling still running. They are not per project; the backend must set a per-project limit itself. CostBudget exists (not in 5.4).
9. `Verified` is implemented, not a stub (old note wrong). DesignLoop registers it itself; ToolLoop does not, so the backend need not pass it (5.4 is silent on it).
10. RequireApproval(tools) takes tool names or `effect:<effect>` rules. geomind does not pick heavy tools: Permissions(mode="ask") asks for every write, execute and external tool, and RequireApproval adds named ones. 5.4 says "geomind decides which", which holds only through effects.
11. Study tools leave no study record (5.2 `study.started_by` and 5.4's last bullet). Only `size_plant` and `optimize` store `design/<name>`; `simulate` stores `result/<id>` and its parts; `sample_uncertainty`, `sensitivity` and `compare` store nothing and return output only. No study event exists, so the backend cannot list agent studies.
12. Run artifacts are scoped to the root run (`state.root`). A chat's second message cannot read the case files, designs or results of the first run. plan.md lists this as open and says "decide with Sahand before the backend stores chats"; the shared contract says chat-scoped artifacts were decided 2026-11-02. These conflict and need Sahand.
13. Geomind's contracts.md (file 15, interface 2.5) and app-frontend-backend.md 5.2 ("contract version 18") are behind the shared contract (file 19, interface 2.6).
14. No difference: the 10 public SSE event types and their `data()` keys match 5.2 and events.md; `agent` and `parent` are always present. The resume answer shapes match 5.4 (`{approved, reason?}` or `{text}`).

## gd.Run (geomind/run.py)

- `Run(message=None, *, chat=None, project=None, history=(), llm=None, store=None, workspace=None, sandbox=None, permissions=None, callbacks=(), hooks=(), agent=None)`. `llm=None` builds `OpenRouter()`; `store=None` builds `MemoryRunStore()`; `permissions=None` builds `Permissions(mode="ask")`. A `Cancellation(lambda: self._is_cancelled)` hook is always appended after the given hooks. `sandbox` given: routed agent is CodeAssistant, else Analyst.
- `Run.load(run_id, *, llm=None, store=None, workspace=None, sandbox=None, permissions=None, callbacks=(), hooks=())` (classmethod). Rebuilds the run from `recover(store.load_events(run_id))`, sets chat and project from the stored state, and sets the loop with `loop_for(state)`. The message and history are not restored; a run keeps no sandbox or permissions, so pass them again.
- `astart()`: RunError if `message is None`. Unless the run is routed or has a loop, it routes first (see difference 6). Loads problem via `store.load_state(chat)` in a thread (empty `ProblemState` when chat is None or no state). Returns `RunResult`. A `NotImplementedYet` from the loop becomes `stop_reason="not_implemented"`.
- `start()`: sync form, `asyncio.run(astart())`; RunError inside a running loop.
- `aresume(request_id=None, answer=None)` / `resume(...)`: answer the pending request, or with `request_id=None` continue a run whose process died.
- `cancel()`: sets an in-process flag; cross-process cancellation uses `gd.hooks.Cancellation`.
- `agent=` replaces the routed agent and skips routing; the backend must not pass it. Setting `run.loop` also skips routing.
- Routing: `loop_of(route)` maps `answer` to ToolLoop(Answer), `tool` to ToolLoop(AGENTS[agent]), anything else to DesignLoop(Designer, Verifier). LOOPS = {tool, design}; AGENTS = {analyst, code_assistant}.

## RunResult (geomind/types/results.py)

- Fields: `run_id: str`; `status: str`; `answer: Any = None`; `request: Request | None = None`; `usage: Usage` (default zero; Usage has cached_tokens, cost, input_tokens, output_tokens); `steps: int = 0`; `stop_reason: str | None = None`. Record config: frozen, extra="forbid". No `message`.
- STATUS_OF_STOP: answer->done, finish->done, request->waiting, denied->failed, step_limit->failed, error->failed, not_implemented->failed, cancelled->cancelled. `queued` is the backend's, before start.

## RunStore (geomind/stores/run.py), protocol of 7 methods, sync

Protocol and docstrings, verbatim:

- `save_event(self, run_id, event)`: "Append one event to a run's log."
- `load_history(self, chat_id)`: "Return the user and assistant messages of a chat, oldest first."
- `save_state(self, chat_id, state)`: "Replace the problem state of a chat."
- `load_state(self, chat_id)`: "Return the problem state of a chat, or ``None``."
- `save_artifact(self, run_id, key, data)`: "Save bytes or a JSON value under a key."
- `load_artifact(self, run_id, key)`: "Return an artifact, or ``None``."
- `load_events(self, run_id)`: "Return a run's events in sequence order; recovery and replay read them."
- Protocol docstring: "The store of the backend contract; sync, because geomind calls it from a worker thread."

Not in the protocol: `save_chat_artifact`, `load_chat_artifact` (difference 3).

Implementations:
- `MemoryRunStore()`: in-process dicts (events, histories, states, artifacts keyed by (run_id, key)); deep copies on save and load. Extra method `add_message(chat_id, message)`.
- `FileRunStore(root=".runs")`: `<root>/<run id>/events.jsonl` and `artifacts/`; `<root>/chats/<chat id>/history.jsonl` and `state.json`. Ids are path parts and raise RunError when unsafe (`^[\w.-]+$`). Keys: one name, or `design/<name>`, `result/<name>`, `case/<name>` (the same name rule). Bytes are stored as `<key>.bin`, JSON as `<key>.json`; load tries `.bin` first. Extra method `add_message`.
- `session.save_artifact(key, data)` redacts secrets (as for events) and writes to `state.root`; `session.load_artifact(key)` reads from `state.root`. Nested runs therefore share the root run's artifacts.
- Keys geomind writes: `design/<name>` (JSON plant); `result/<id>` (JSON summary); `<id>.results` (bytes, `Results.to_bytes()`); `<id>.plant` (JSON); `<id>.case` (JSON case dict as the state held it); `<id>.files` (JSON `{file name: sha256}`); `<sha256>.file` (bytes, a case file by content); `case/<file name>` (bytes, a file the run's case names); `result-<16 hex>` (a tool output over 40,000 characters, `tool_result_limit`, from dispatch); `output-<16 hex>` (text from the code tool).

## Workspace (geomind/stores/workspace.py), protocol of 3 methods

- `plant(self, project_id)`: "Return the stored plant as a gemini plant, or ``None``." (FileWorkspace: `gm.Plant.from_json(<root>/<project>/plant.json)`, gemini imported only here.)
- `case(self, project_id)`: "Return the project's case as ``(case dict, folder of its files)``, or ``None``." Docstring continues: "The dict is the content of a ``case.json``, as written; the folder holds the files it names."
- `documents(self, project_id, query)`: "Return matching documents as ``[{id, title, text, score}]``, best first."
- Implementations: `MemoryWorkspace(plants=None, documents=None, cases=None)`, where `cases={project: (dict, folder)}`; `FileWorkspace(root)` reads `<root>/<project>/plant.json`, `<root>/<project>/case.json` (the folder returned is `<root>/<project>` itself) and `documents/*.md|*.txt`. `search()` is keyword count.

Semantics of `Workspace.case` and case files by content:
- The dict is the case as written, never `gm.Case.to_dict()` (that does not round-trip the demand). geomind validates it with `gm.Case.from_dict`.
- Files: `set_case(source="project")` reads every file the case names (any string `file` key, recursively). Each name must be a bare file name; a name missing from the folder raises ToolError `unknown_name`.
- The bytes are copied into the run as `case/<name>`. `case_origin` keeps `{case, files: {name: sha256}}`, and each file is kept once as `<sha256>.file`, so a file overwritten later never changes what an older run reads. Identity of a file is its content digest.
- `<id>.files` holds the digests a run used; `Verified` compares them with the current state's files (`result_off_case`). A change of a file's content is a change of the case (`case_changed`).
- `check_workspace` needs a project whose case has `time` and a `demand.file` present in the folder.

## Case integrity: what the backend must do

1. `Workspace.case(project)` returns the case.json content exactly as written, and a folder holding each named file under its bare name. Otherwise `set_case(source="project")` fails.
2. Problem state: `save_state`/`load_state` store the dict as given. It holds `case`, `case_origin` and `compaction`. Never edit it: `update_state` cannot write `/case` or `/case_origin`.
3. RunStore must return bytes and JSON exactly as written, and keep `.bin` and `.json` apart. A missing `case/<name>` is silently absent from `file_contents`, and the build then fails.
4. A run's `<id>.case` and `<id>.files` are compared with the state's case, so a changed case makes an older result stale; do not rewrite case values in storage.
5. The case the user gave (the first case of a chat, or `source="project"`) is `case_origin`; changes need the user's approval (`accept_case`, driver only).
6. Gap: a second message in a chat reads `state.case` but not its files, until chat-scoped artifacts exist (difference 12).

## Events (geomind/types/events.py)

- Public (10): run.started {run, loop}; step.started {index, model}; text.delta {index, text}; tool.started {index, call_id, tool, input}; tool.finished {index, call_id, output_summary, duration, error?}; step.finished {index, usage, text}; state.changed {version, changes}; request {request, call_id?, kind, message, options?}; usage {input_tokens, output_tokens, cost}; run.finished {status, stop_reason, message?}.
- Internal (8): llm.completed, compaction, tool.result, permission, retry, sandbox.provisioned, sandbox.closed, error. Stored, never streamed.
- `event.data()` drops `None` optional fields and always adds `agent` and `parent`. `event.to_dict()` adds `type` and every field.
- `event_from_dict(data)`: pops `type`; unknown type raises RunError.
- Stored extras: `RunStarted` (root, agent_class, max_steps, chat, project, parent_step, messages, problem, settings, loop_state); `RequestMade` (point, call); `RunFinished` (answer); `StepFinished` (loop_state).
- `text.delta` goes to callbacks only, never to the store.

## gd.runlog (geomind/types/runlog.py)

`runlog(events)` returns `{run: {id, chat, status, loop, started, ended, usage}, steps: [{index, agent, parent, llm_calls, tool_calls}]}`. RunError if there is no root `run.started`. `tool_call.error` is `True` only on error.

## gd.Permissions (geomind/engine/permissions.py)

`Permissions(mode="ask", allow=(), ask=(), deny=())`. Modes: auto, ask, readonly, plan. Effects: read, compute, write, execute, external. Rules: tool name or `effect:<effect>`. Order: deny -> mode limit (plan denies all; readonly denies non-read/compute) -> ask rules (and hook ask rules) -> allow rules (plus default `update_state`) -> mode default (ask asks for non-read/compute). Every decision is a `permission` event.

## Hooks (geomind/engine/hooks.py)

- `gd.hooks.Hook`: override `before_llm_call(context, agent, messages)`, `before_tool_call(context, agent, call)`, `before_finish(context, agent, action)`; plain or async; return None, Deny, Request, Allow(input=...) for tool calls. The first objection wins.
- `TokenBudget(max_tokens)`: denies an LLM call once input+output tokens of the run tree reach the limit (`context.session.total_usage`).
- `CostBudget(max_cost)`: the same on cost.
- `RequireApproval(tools)`: ask rules for the named tools or effects.
- `Cancellation(is_cancelled)`: checked before every LLM call, tool call and the answer; ends the run with `cancelled`; `always_asked = True`.
- `Verified()`: no arguments; refuses the answer while the design's stored run fails `gd.verify.verify`; a nested run defers to its parent. Registered by DesignLoop.

## Providers (geomind/providers/)

- LLM protocol: `complete(messages, tools, *, model, settings, on_text=None)`.
- `OpenRouter(api_key=None, base_url=..., transport=None)`: see difference 7. request_timeout 120 s; retry_count 3 (RetryLLM, added by the engine); prompt caching on Anthropic models.
- `FakeLLM(completions)` (geomind/providers/fake.py, exported from `gd.providers`, not `gd.testing`): returns scripted Completions or raises scripted exceptions; calling past the end raises ProviderError; `calls = [{messages, tools, model}]`; `FakeLLM.from_events(events)` (skips the rule-model completions); `FakeLLM.from_recording(path)` (one Completion JSON per line).
- `Recorder(llm, path)`: appends each completion, without `raw`, to a JSONL recording.

## Testing helpers (gd.testing)

`gd.testing` exports only two functions (geomind/testing/conformance.py):
- `check_run_store(factory, seed_history=None)`: `factory()` returns a fresh store. Checks event order and `load_events` (missing run -> []), history (only if `seed_history(store, chat_id, messages)` is given), state (round-trip, replace, missing -> None), and artifacts (bytes, JSON, `design/`, `result/`, `case/conformance.csv`, per-run isolation). It does NOT check chat-scoped artifacts.
- `check_workspace(factory, *, project, query, missing_project="conformance-missing")`: the factory holds a plant, a case with a demand file in its folder, and a document matching `query`. Checks plant, case, documents (fields id/title/text/score, best first) and unknown projects.

## Study tools (geomind/tools/gemini/study.py, stored.py)

- `size_plant(design, backup, name)` (compute): stores `design/<name>`; returns `{design, sizing}`.
- `optimize(design, objective, variables, evaluations, name, constraints?)` (compute): stores `design/<name>` only when a best plant exists; returns `{best, feasible, fixed, trials, design?}`. Trials are not stored.
- `sample_uncertainty(design, metrics, count, seed)`, `sensitivity(design, metrics)`, `compare(references, by)`: store nothing; return output only.
- `simulate` (through stored.save_run): stores `result/<id>` and `<id>.results`, `<id>.plant`, `<id>.case`, `<id>.files`, and `<sha256>.file` per case file. The id is a hash of plant, case, files and options.
- Timeout STUDY_TIMEOUT_S = 900; a timed-out study returns a `timeout` error.

## Plan.md: chat-scoped artifacts and gemini requests

- Chat-scoped artifacts: plan.md section 7, Open, first bullet. It says the second message of a chat loses the case's files (`read_profile` fails with `demand.csv not found`) and a design or result named in the state is unreadable. It says fixing it changes the backend contract: "a chat-scoped artifact space, or the state naming the run that holds each artifact. Decide with Sahand before the backend stores chats." It does not describe any chat-scoped method as built.
- "Three gemini requests": plan.md section 7 lists twelve requests to gemini. Commit eeb80d9 ("the chat-scoped artifacts gap and three gemini requests are open work") added requests 10, 11 and 12: one public verdict shared by `minimize` and geomind; `gm.evaluate` copies the plant per metric (speed); `Comparison.to_dict()` in display units.

## API rules

api.json (version 0.2.0) pins: Run (signature of `__init__`, `aresume`, `astart`, `cancel`, `load`, `resume`, `start`), RunResult, protocols (LLM, RunStore, Sandbox, SandboxProvider, Workspace), Permissions, hooks (Cancellation, CostBudget, Hook, RequireApproval, TokenBudget, Verified), stop_reasons, answers, events, runlog, Callback, Completion, Message, Usage, `all` (public names) and the version. A change to a frozen interface raises the minor version (0.x semver rule).

## Update: geomind 0.3.0 (989cb59), D3

- Difference 3 and 12 are resolved upstream: `save_chat_artifact` / `load_chat_artifact` exist, a chat's space and a run's are separate, and `check_run_store(factory, seed_history)` and `check_workspace` test them.
- Backend: a chat artifact is a `run_artifacts` row with `run_id` null (migration 0008); `newest_for_chat` reads only those rows. A run's artifacts keep both ids and are read by run. Both conformance checks pass in `tests/api/v1/assistant/runs/test_adapters.py`.
- Installed: gemini 0.5.0 (217625e), geomind 0.3.0 (989cb59); `requirements.txt` installs both editable from the sibling checkouts, so no range changes.
