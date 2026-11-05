# Changelog

The backend and its API contract (`docs/app-build/contracts.md`) share one version,
`major.minor.patch`, set in `src/version.py`, the same scheme as the frontend. For now every
release stays on 1.1 and raises only the patch: 1.1.0, 1.1.1 and on (Sahand, 2026-11-03). Each
release is tagged `v<version>` on `main`. Work goes to `dev` first and reaches `main` when its
tests pass.

## [1.1.80] - 2026-11-05

- QA-088: `GET /design/study/{id}/agent-record` returns what an agent stored for a study it ran
  (tool, method, designs, result as the tool stored it); agent studies had only an "Open run"
  link. A done agent study shows its progress whole instead of "-". Note: `filters_sized` is a
  `size_plant` record: sizing only, no simulation, so it has no results. Hotfix mode: no tests ran.

## [1.1.79] - 2026-11-05

- QA-081: geomind 0.4.73's `AlreadyAnsweredError` on a resume is caught by its class: "the run
  goes on" skips the resume, "the run waits on 'request-X'" puts the run back to wait on X; the
  older text match stays for earlier geomind. Hotfix mode: no tests ran.

## [1.1.78] - 2026-11-05

- QA-081, QA-087: geomind 0.4.73 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.73-py3-none-any.whl`):
  `gd.errors.AlreadyAnsweredError` for a second answer to a settled request; web_search capped
  at six searches per agent and run.

## [1.1.77] - 2026-11-05

- QA-081 (reopened, run 753645c0): an answer to a request that already has a person's decision is
  refused with `409 conflict`; a resume geomind refuses as "unknown or already answered" is
  logged and skipped instead of failing the run (the run goes on in its own process). Hotfix
  mode: only test_boundaries ran.

## [1.1.76] - 2026-11-05

- QA-082: geomind 0.4.72 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.72-py3-none-any.whl`):
  simulate's summary no longer fails on an ESP failure group (it listed the case's values as
  missing although the run had run).

## [1.1.75] - 2026-11-05

- QA-082, QA-083: gemini 0.6.10 and geomind 0.4.71 as local wheels (`.tmp/hotfix-wheels/`):
  the check names a doublet's missing depth first; simulate changes set the plant's options
  (control.dispatch, outages, backup); a bare inlet name is a coded error; an unexpected tool
  exception reaches the agent with its class, message and place.

## [1.1.74] - 2026-11-05

- QA-081: a run geomind refuses to build or go on with (for example a resume whose request is
  unknown or already answered) ends with `stop_reason` and `error.code` `geomind_refused` and
  geomind's message, and the worker logs it; it ended as `error` with nothing in the log, and the
  chat showed "internal error in geomind". Hotfix mode: no tests ran.

## [1.1.73] - 2026-11-05

- QA-080: gemini 0.6.8 and geomind 0.4.69 as local wheels (`.tmp/hotfix-wheels/`): a doublet's
  flow range is read over all its flow requirements (two one-sided rules make one range); the
  case lead writes a two-ended range as one rule.

## [1.1.72] - 2026-11-05

- QA-076, QA-078: geomind 0.4.68 and gemini 0.6.7 as local wheels (`.tmp/hotfix-wheels/`):
  gm.check returns an incomplete plant's issues again (no more missing_value failures of
  read_plant/build_plant/patch_plant); engineers may write their own parts; calculation ids are
  unique and a corrupted state with repeated ids loads again.

## [1.1.71] - 2026-11-05

- QA-072: geomind 0.4.66 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.66-py3-none-any.whl`):
  agents never attribute to the user what the user did not write.

## [1.1.70] - 2026-11-05

- QA-077: a run row never leaves `done`, `failed` or `cancelled` for `waiting` or `running`
  (the recorder and the stale-answer path skip such a write); a `waiting` run whose log already
  ended (a root `run.finished` newer than its last `request`) is ended with that status when it
  is read (`GET /assistant/runs/{id}`, answer, cancel) or when its chat gets a new message, so a
  stuck chat such as 81b51db5 frees itself. Hotfix mode: only test_boundaries ran.

## [1.1.69] - 2026-11-05

- QA-071 and the evolve structures view: geomind 0.4.65 and gemini 0.6.6 as local wheels
  (`.tmp/hotfix-wheels/`): web_search English only with short one-value queries;
  `gm.study.structure_plant(plant, structure, parameters)` builds the plant of any evolve structure.

## [1.1.68] - 2026-11-05

- `GET`/`POST /design/study/{id}/structures/{rank}/plant` serve every structure: a plant gemini
  did not store is built with `gm.study.structure_plant` (gemini 0.6.6) from the study's input
  plant (its plant version, or the agent's design artifact); `404 structure_plant_not_stored`
  only when it cannot be built. Hotfix mode: no tests ran.

## [1.1.67] - 2026-11-05

- `GET` and `POST /design/study/{id}/structures/{rank}/plant`: open the plant of a ranked evolve
  structure, or save it as the project's next plant version. gemini keeps a plant only for the
  best design and the Pareto front; another structure gives `404 structure_plant_not_stored`
  (building it needs a public gemini function). Hotfix mode: no tests ran.

## [1.1.66] - 2026-11-05

- `GET /design/study/{id}/structures?limit=10` (1-50): the best design of each structure of an
  evolve study, ranked as gemini ranks (smaller violation first, then the objectives in their
  direction), from `Evolution.to_dict()` stored at the result's `run.found` (page studies) or in
  the agent's `study/<name>` artifact: `{study, name, objectives, budget, total, structures: [{rank,
  structure, evaluations, feasible_evaluations, feasible, reason, violation, metrics,
  parameters, on_front}]}`; `404 structures_not_found` for another kind or no stored result.
  Hotfix mode: no tests ran.

## [1.1.65] - 2026-11-05

- QA-047, QA-070: geomind 0.4.64 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.64-py3-none-any.whl`):
  teammates' answers kept as findings in the problem state (new `findings` list); a nested agent
  left open by a worker restart runs again on resume instead of failing at 0 s.

## [1.1.64] - 2026-11-05

- QA-069: geomind 0.4.62 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.62-py3-none-any.whl`):
  `set_case` returns `plants_need`, the case values the project's plants still lack.

## [1.1.63] - 2026-11-05

- Agent tools step 4: geomind 0.4.61 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.61-py3-none-any.whl`):
  skills connectors, economics, report, comparing-designs take sometimes-needed how-to out of four
  role prompts; skill lists show only skills for the agent's tools.

## [1.1.62] - 2026-11-05

- QA-068: a run the model provider refused (HTTP 401, 402, 403 or 429 in geomind's failure, such
  as OpenRouter's 403 "Key limit exceeded") ends with `stop_reason: provider_refused` and a clear
  message ("The model provider refused: key limit exceeded; an admin must raise it.") in the live
  and replayed `run.finished` and in the run's `error`; the chat showed "internal error in
  geomind". Hotfix mode: no tests ran.

## [1.1.61] - 2026-11-05

- QA-065, QA-061: geomind 0.4.60 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.60-py3-none-any.whl`):
  the brief's doublet-count limit becomes a requirement and the design lead cites only the case's
  requirements; question cards show no internal already-answered note.

## [1.1.60] - 2026-11-05

- `GET /assistant/runs/{id}/calls/{call_id}`: one tool call's full stored output
  `{call_id, tool, agent, status, source, input, output}`, for the new tool views (calculate,
  run_python, web_search); `404 call_not_found` for an unknown call. Hotfix mode: no tests ran.

## [1.1.59] - 2026-11-05

- QA-058: a person's decision on a request is a public `answer` event, live and on replay (its id
  is the sequence of geomind's internal event it comes from, so a reload shows the same record):
  `{request, kind, message, tool, call_id, decision, reason, text, by, time}`; `decision` is
  `allow`, `deny` or `answer` (typed text in `text`). Hotfix mode: no tests ran.

## [1.1.58] - 2026-11-05

- Agent tools step 3: geomind 0.4.58 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.58-py3-none-any.whl`):
  `web_search` and `read_web_page` (effect `external`) over SearXNG at `GEOMIND_SEARCH_URL`;
  `calculate` takes plain numbers and constants beside one sourced operand.

## [1.1.57] - 2026-11-05

- Agent tools step 2: geomind 0.4.57 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.57-py3-none-any.whl`):
  `run_python` (effect `execute`) in the docker sandbox the worker starts (`ASSISTANT_SANDBOX=docker`,
  `GEOMIND_SANDBOX_*`); `build_sandbox` now passes `gd.sandbox.DockerSandbox()`.

## [1.1.56] - 2026-11-05

- Agent tools step 1: geomind 0.4.56 as a local wheel (`.tmp/hotfix-wheels/geomind-0.4.56-py3-none-any.whl`):
  skills folder with roles and the `calculate` tool (effect `compute`); its result is kept in the
  problem state's new `calculations` list.

## [1.1.55] - 2026-11-05

- Agent tools (feature agent-tools-2026-11-05): the worker container gets the docker CLI and the
  host's docker socket (group `DOCKER_GID`) for geomind's `run_python` sandbox
  (`ASSISTANT_SANDBOX=docker`, `GEOMIND_SANDBOX_IMAGE`, `GEOMIND_SANDBOX_TIMEOUT`, `_MEMORY`,
  `_DISK`, `_CPU`); `GEOMIND_SEARCH_URL` points `web_search` at SearXNG
  (`../infrastructure/searxng`, internal only). New keys in both env examples. Hotfix mode: no
  tests ran (test_env_examples.py passed).

## [1.1.54] - 2026-11-05

- gemini 0.6.5 from the local wheel `.tmp/hotfix-wheels/gemini_geothermal_suite_open-0.6.5-py3-none-any.whl`
  (dev b20c2964, tag v0.6.5): `gm.check` names the plant rules and a split well's pump depth
  (QA-040), humidity takes `%` (QA-043), a local daily series is matched by date (QA-039), unit
  problems carry `quantity` and `accepted`. With geomind 0.4.55 (tag v0.4.55, commit c3b167c).
  Hotfix mode: no tests ran.

## [1.1.53] - 2026-11-05

- QA-011, QA-013: geomind 0.4.54 from the local wheel
  `.tmp/hotfix-wheels/geomind-0.4.54-py3-none-any.whl` (tags v0.4.53, v0.4.54, commit edd7927):
  a nested run a provider failure stopped is run again once; `ask_economics` fills the
  recommended catalogue rows itself (geomind 0.4.52's sourced catalogue included). Hotfix mode:
  no tests ran.

## [1.1.52] - 2026-11-05

- QA-049: the plant's problems and a study's missing list name, first, every plant-level value
  with no value (such as `params.depth`, "with it each doublet takes its reservoir values from
  the case", and `params.backup`); gemini's check did not name `depth`, so the plant asked for the
  reservoir values the case already has. Hotfix mode: no tests ran.

## [1.1.51] - 2026-11-05

- QA-050, QA-009: geomind 0.4.51 from the local wheel
  `.tmp/hotfix-wheels/geomind-0.4.51-py3-none-any.whl` (tags v0.4.50, v0.4.51, commit 5ed3269):
  read-only MCP calls wait out a rate limit; an approve-all answer leaves open keys open. Hotfix
  mode: no tests ran.

## [1.1.50] - 2026-11-05

- QA-031: auto-approve is stored per chat in the backend: `GET` and `PUT
  /assistant/chat/{chat_id}/auto-approve` with `{"auto_approve": bool}` (kept in Redis, no
  migration; a lost key reads as off). A run started or resumed while it is on runs with geomind's
  permission mode `auto`, so tool calls run with no tab open, nested agents' included. Hotfix
  mode: no tests ran.

## [1.1.49] - 2026-11-05

- QA-055: geomind 0.4.49 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.49-py3-none-any.whl`
  (tag v0.4.49, commit ddeb5be): an ESP with no curve is `unspecified` and the doublet derives its
  curves; no question for a pump curve. Hotfix mode: no tests ran.

## [1.1.48] - 2026-11-05

- QA-056 (root cause): a waiting run's `request` follows the newest stored `request` event of the
  run tree whenever the run is read (`GET /assistant/runs/{id}`), answered or cancelled; the row
  had kept an older request (3455 after the case lead asked 3519), so the chat showed the old one.
  Hotfix mode: no tests ran.

## [1.1.47] - 2026-11-05

- QA-016, QA-052, QA-054: geomind 0.4.48 from the local wheel
  `.tmp/hotfix-wheels/geomind-0.4.48-py3-none-any.whl` (tags v0.4.47, v0.4.48, commit 7a82fcf):
  a side-by-side engineer called alone never waits for an approval; bare-string plant options are
  taken; no bug ids in the prompts. Hotfix mode: no tests ran.

## [1.1.46] - 2026-11-05

- QA-056: an answer to a request that is not geomind's pending one no longer fails the run: when
  geomind refuses it ("expected 'request-N'"), the run waits again on the pending request, read
  from its stored `request` event, and the chat receives that request again. A refused answer's
  422 names the request the run waits on. Hotfix mode: no tests ran.

## [1.1.45] - 2026-11-04

- QA-010: geomind 0.4.46 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.46-py3-none-any.whl`
  (tag v0.4.46, commit eb90156): delegated open values are searched for, then proposed as
  engineering assumptions for the user to approve. Hotfix mode: no tests ran.

## [1.1.44] - 2026-11-04

- QA-046: the run's totals grow while a nested agent works: the run row and a live root `usage`
  event (no `id`) carry the root's last totals plus the latest totals of each running nested run;
  before, they stayed flat until the nested run ended and then jumped. Hotfix mode: no tests ran.

## [1.1.43] - 2026-11-04

- QA-045, QA-047: geomind 0.4.45 from the local wheel
  `.tmp/hotfix-wheels/geomind-0.4.45-py3-none-any.whl` (tags v0.4.44, v0.4.45, commit 5ec7d83):
  `ask_economics` leaves out a catalogue row with no 2015 value; after a stopped run the leads go
  on from the stored design. Hotfix mode: no tests ran.

## [1.1.42] - 2026-11-04

- QA-044: an empty or non-numeric `Last-Event-ID` starts the run's stream from the beginning
  instead of a 422 `validation_failed`, which stopped the chat's live stream for good after a
  reconnect. Hotfix mode: no tests ran.

## [1.1.41] - 2026-11-04

- QA-043: geomind 0.4.43 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.43-py3-none-any.whl`
  (tag v0.4.43, commit 9c30cd2): the case lead says a server humidity in % is not usable and asks
  for the fraction. Hotfix mode: no tests ran.

## [1.1.40] - 2026-11-04

- QA-042: geomind 0.4.42 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.42-py3-none-any.whl`
  (tag v0.4.42, commit 3334d64; holds 0.4.33 to 0.4.41 too): a files-only `set_case` after a full
  one is refused with the step of that call to send again whole. Hotfix mode: no tests ran.

## [1.1.39] - 2026-11-04

- QA-040: the plant's own choice parameters (gemini's plant `describe()`, e.g. `backup`: `peak` or
  `none`) are listed by `GET /plant/parameters/plant` with `options` and set by
  `POST /plant/parameters/plant` `values`; a choice with more than one option and no value is
  named as a `missing_value` problem of the plant (gemini's check did not name `params.backup`,
  and sizing refused the study). Hotfix mode: no tests ran.

## [1.1.38] - 2026-11-04

- QA-041: geomind 0.4.41 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.41-py3-none-any.whl`
  (tag v0.4.41, commit 03e776b; holds 0.4.33 to 0.4.40 too): the economics rows follow the site's
  country, and bounds or proxies are not recommended. Hotfix mode: no tests ran.

## [1.1.37] - 2026-11-04

- QA-037: geomind 0.4.40 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.40-py3-none-any.whl`
  (tag v0.4.40, commit 52777ef; holds 0.4.33 to 0.4.39 too): `set_case` is checked by gemini
  before the user is asked to approve it. Hotfix mode: no tests ran.

## [1.1.36] - 2026-11-04

- QA-034: geomind 0.4.39 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.39-py3-none-any.whl`
  (tag v0.4.39, commit 7bc46ff; holds 0.4.33 to 0.4.38 too): the case lead no longer offers a
  demand from a peak and an annual energy. Hotfix mode: no tests ran.

## [1.1.35] - 2026-11-04

- QA-032: a CSV added to the case (`POST /design/case/files`) whose first column is named
  `date`, `datetime` or `timestamp` is saved with that column named `time`, the name gemini's
  series reader takes; the competition's demand files work on the Case page as given. Hotfix
  mode: no tests ran.

## [1.1.34] - 2026-11-04

- QA-023: geomind 0.4.38 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.38-py3-none-any.whl`
  (tag v0.4.38, commit d804283; holds 0.4.33 to 0.4.37 too): a project with a `ready` case gets
  the plant's next steps. Hotfix mode: no tests ran.

## [1.1.33] - 2026-11-04

- QA-020: geomind 0.4.37 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.37-py3-none-any.whl`
  (tag v0.4.37, commit 537a317; holds 0.4.33 to 0.4.36 too): the side-by-side engineers read the
  case and the plant once. Hotfix mode: no tests ran.

## [1.1.32] - 2026-11-04

- QA-018: geomind 0.4.36 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.36-py3-none-any.whl`
  (tag v0.4.36, commit 1105419; holds 0.4.33 to 0.4.35 too): the process engineer takes a plant
  class's modules as `read_plant` gives them. Hotfix mode: no tests ran.

## [1.1.31] - 2026-11-04

- QA-014: geomind 0.4.35 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.35-py3-none-any.whl`
  (tag v0.4.35, commit a6a4595; holds 0.4.33 and 0.4.34 too): `read_case` of an unset section
  answers `unset` instead of an error. Hotfix mode: no tests ran.

## [1.1.30] - 2026-11-04

- QA-012: geomind 0.4.34 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.34-py3-none-any.whl`
  (tag v0.4.34, commit a682362; holds 0.4.33 too): an answer the provider ends early gets a true
  note instead of "cut at the output limit". Hotfix mode: no tests ran.

## [1.1.29] - 2026-11-04

- QA-035: when the worker starts, a run still `running` that started within 12 hours is resumed
  from its event log (`assistant.runs.resume` with no request; geomind continues a run whose
  process died), so a deploy no longer ends long agent runs. Older ones are still ended as
  failed/interrupted (QA-017). Hotfix mode: no tests ran.

## [1.1.28] - 2026-11-04

- QA-002: geomind 0.4.33 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.33-py3-none-any.whl`
  (tag v0.4.33, commit 02a8364): the case lead writes efficiencies as fractions with no unit.
  Hotfix mode: no tests ran.

## [1.1.27] - 2026-11-04

- QA-026: geomind 0.4.32 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.32-py3-none-any.whl`
  (tag v0.4.32, commit 97dbbe1; holds 0.4.30 and 0.4.31 too): an approval's message shows the
  call's input, so the approval card shows what `set_case` writes. Hotfix mode: no tests ran.

## [1.1.26] - 2026-11-04

- QA-015: geomind 0.4.31 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.31-py3-none-any.whl`
  (tag v0.4.31, commit fa8c813; holds 0.4.30 too): the design stops on a case value gemini names
  as missing and the case lead asks for it first. Hotfix mode: no tests ran.

## [1.1.25] - 2026-11-04

- QA-016: geomind 0.4.30 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.30-py3-none-any.whl`
  (tag v0.4.30, commit b6f61d6): a `fill_parts` engineer's approval is allowed instead of coming
  back as output, so the run no longer stays `waiting` and the engineer's work is kept. Hotfix
  mode: no tests ran.

## [1.1.24] - 2026-11-04

- QA-024: the API rate limit counts per sign-in (the verified access token), not per user, so
  browsers signed in as the same user no longer share 100 requests a minute; requests without a
  user count per visitor address (`CF-Connecting-IP`), not per proxy. Hotfix mode: no tests ran.

## [1.1.23] - 2026-11-04

- QA-021: a failed model call that geomind retries is streamed to the chat as a live `retry`
  event `{attempt, model, delay, status}` (never stored; the HTTP status only, no provider text),
  so the chat can say the provider is busy instead of only Thinking. Contract: the `retry` row of
  the live event table. Hotfix mode: no tests ran.

## [1.1.22] - 2026-11-04

- Every geomind role runs on `deepseek/deepseek-v4.1-flash-1017` with the OpenRouter provider
  `morph/fp8` first (`GEOMIND_PROVIDER=morph/fp8`); `ASSISTANT_MODEL_PREFIX` defaults to that
  model; `.env.example` sets all 17 roles to it. Hotfix mode: no tests ran.

## [1.1.21] - 2026-11-04

- Every geomind role runs on `~deepseek/deepseek-flash-latest` (OpenRouter's alias of the latest
  DeepSeek flash model), no longer nemotron: `ASSISTANT_MODEL_PREFIX` defaults to it,
  `.env.example` sets all 17 roles to it, `GEOMIND_PROVIDER=deepseek`. Hotfix mode: no tests ran.

## [1.1.20] - 2026-11-04

- QA-009: geomind 0.4.29 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.29-py3-none-any.whl`
  (tag v0.4.29, commit 0622c67; it holds the QA-004 fix of 0.4.28 too): every `ask_user` answer
  is kept in the problem state, so no agent asks the same question again. Hotfix mode: no tests
  ran.

## [1.1.19] - 2026-11-04

- QA-017: when the worker starts, every run still `running` is ended as failed (code
  `interrupted`, "The run stopped because the app was updated or restarted; send your message
  again."), with its `run.finished` event; a deploy no longer leaves a run active forever. Queued
  and waiting runs stay. Hotfix mode: no tests ran.

## [1.1.18] - 2026-11-04

- QA-004: geomind 0.4.28 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.28-py3-none-any.whl`
  (tag v0.4.28, commit 64ac883): `ask_economics` checks a key that takes no unit before the user
  is asked (`kg CO2e/kg CH4` on the CH4 GWP is set with no unit). Hotfix mode: no tests ran.

## [1.1.17] - 2026-11-04

- QA-007: geomind 0.4.27 from the local wheel `.tmp/hotfix-wheels/geomind-0.4.27-py3-none-any.whl`
  (tag v0.4.27, commit 68e7bb2): `ask_economics` leaves out a key that is not an economics key
  with a note instead of refusing the whole question. Hotfix mode: no tests ran.

## [1.1.16] - 2026-11-04

- Every geomind role runs on `nvidia/nemotron-3.5-super-vl:free` (OpenRouter), no longer DeepSeek:
  `ASSISTANT_MODEL_PREFIX` defaults to it, `.env.example` sets all 17 `GEOMIND_<ROLE>_MODEL` to
  it, `GEOMIND_PROVIDER` is empty (OpenRouter chooses), `GEOMIND_CONTEXT_WINDOW=200000`. Hotfix
  mode: no tests ran.

## [1.1.15] - 2026-11-04

- geomind 0.4.26, pinned by URL and sha256: next-step suggestions are always English (no Persian
  labels). The tests write their Persian sample text escaped, so no file holds Persian text.
  Hotfix mode: no tests ran.

## [1.1.14] - 2026-11-04

- geomind 0.4.25, pinned by URL and sha256. Fixes run 86ddac2a: the case lead's `ask_economics`
  call ran past the model's output limit three times and the run stopped without economics. The
  case lead now names catalogue rows by id and geomind reads their values from the knowledge base
  (`cost-sources.csv`); a completion at the output limit gets the cut note. No migration, no new
  settings.

## [1.1.13] - 2026-11-04

- Fix: every run that geomind led as a project failed with an internal error when the project
  had memory on. geomind asks the workspace for the memory before the run knows its project,
  so the workspace got no project id; it now uses the run's own project (or memory off).

## [1.1.12] - 2026-11-04

- geomind 0.4.24 and gemini 0.6.4, pinned by URL and sha256. geomind needs
  `GEOMIND_EVOLVE_STOP_GENERATIONS` and `GEOMIND_EVOLVE_STOP_SECONDS` (a number or `off`); a live
  run without them is refused naming them. Both examples set them to `off`, and so do the tests.
  The sandbox image follows the installed gemini (`gemini-sandbox:0.6.4`).
- `GET /assistant/runs/{id}` has `sessions`, `agents` and `total`: geomind's per-session, per-agent
  and run-tree figures (`cached_tokens` included), read from the root run's stored `run.finished`.
  They are null for a run still going, for a run logged before geomind 0.4.24, and in every other
  answer that holds a run (the runs list, answer, cancel, the overview, a message's run). No
  migration.
- Live and replayed events (SSE and WebSocket) carry geomind 0.4.24's new fields as they come:
  `step.started.session`, `step.finished.context` and per-call `usage.cached_tokens`, and the root
  `run.finished.sessions` / `agents` / `total`. `/agents` reads these keys as geomind's event
  classes name them.
- New geomind codes: a Connector Check whose server refuses the request's arguments (JSON-RPC
  -32602) fails with `invalid_arguments`, no longer `bad_response`; `invalid_unit` (and
  `memory_unavailable`, `invalid_input`) reach `tool.finished.problem` like the other tool codes.
- `python -m scripts.knowledge add` replaces every shared Knowledge document of the file's name,
  older copies uploaded on the Knowledge page included, so a search finds only the new text.

## [1.1.11] - 2026-11-04

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
- `ASSISTANT_RUN_MAX_TOKENS` may be `off`: no token cap for a run. It caps the whole run's tokens
  over every call and sub-run (a cost guard), never an agent's context.
- Production reads a plain `.env` (`compose.yml`), no longer `.env.production`. The tests read
  `.env.example` (`APP_ENV_FILE`), never `.env`. `.env.example` and `.env.dev.example` name the
  same settings, with `ASSISTANT_RUN_MAX_TOKENS` in both.

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
