# Changelog

The backend and its API contract (`docs/app-build/contracts.md`) share one version,
`major.minor.patch`, set in `src/version.py`, the same scheme as the frontend. For now every
release stays on 1.1 and raises only the patch: 1.1.0, 1.1.1 and on (Sahand, 2026-11-03). Each
release is tagged `v<version>` on `main`. Work goes to `dev` first and reaches `main` when its
tests pass.

## [1.1.132] - 2026-11-05

- QA-274, QA-215: chat studies without a simulate get a result on the latest case, with their plant version.
- geomind 0.4.136+ (QA-351, 352, 353, 248, QA-354 part a), gemini 0.6.34.

## [1.1.131] - 2026-11-05

- QA-350: the projects list and search are newest first; the cursor pages in that order.
- geomind main HEAD.

## [1.1.130] - 2026-11-05

- QA-292: per-user auto-approve preference (GET/PUT /assistant/preferences; migration 0015, users.auto_approve).
- QA-341: an ended run keeps one line per agent session (`instances`).
- QA-336: a waiting run's pending request is asked again as the last event when read.
- geomind main HEAD.

## [1.1.129] - 2026-11-05

- geomind main HEAD (QA-349, QA-346), gemini dev HEAD.

## [1.1.128] - 2026-11-05

- QA-338: report section 7 describes optimisation results; unmet energy below 0.01 % reads 'All demand is met.'
- geomind main HEAD (QA-339 auto-answers, QA-343), gemini 0.6.34 (QA-343, QA-260, QA-335 revert).

## [1.1.127] - 2026-11-05

- QA-336: events of a resumed run whose sequence collides are renumbered after the stored maximum; the question card shows.
- geomind main HEAD (QA-336 geomind part, QA-337, QA-278), gemini dev HEAD.

## [1.1.126] - 2026-11-05

- QA-328: progress.plant is incomplete when designs exist only in results.
- gemini 0.6.33 (QA-335: reverts the cooler sizing of 0.6.32), geomind main HEAD (QA-330, 331, 320, 333).

## [1.1.125] - 2026-11-05

- QA-332: studies no longer fail on gemini 0.6.31 coverage days ('bool' has no to_dict).
- QA-322: coverage days carry electricity, no_demand and labels; report day counts use them.
- QA-325: the report states what the checks cover. QA-323: fuel and produced gas burned in the energy table.
- geomind main HEAD, gemini dev HEAD (0.6.32).

## [1.1.124] - 2026-11-05

- No backend change: geomind main HEAD (QA-326 and more), gemini 0.6.31.

## [1.1.123] - 2026-11-05

- QA-313: the design report has numbered sections, subsections, captions and text by every figure and table; PDF and Markdown exports follow.
- QA-194: project progress has an economics item.
- geomind main HEAD (QA-317 and more), gemini dev HEAD.

## [1.1.122] - 2026-11-05

- QA-312: the agents' workspace saves an approved design as the project's next plant version.
- geomind main HEAD, gemini dev HEAD.

## [1.1.121] - 2026-11-05

- QA-310: a cancelled run stores 'Cancelled by the user.' and the user's denials as an assistant message.
- QA-194: project_state reports economics {state}.
- geomind main HEAD, gemini dev HEAD.

## [1.1.120] - 2026-11-05

- QA-294: the agents' project_designs lists every project result, newest first.
- geomind main HEAD (0.4.131), gemini dev HEAD.

## [1.1.119] - 2026-11-05

- QA-239: the results trade-off front counts feasible results only.
- geomind main HEAD 4a946bd (QA-294, QA-295, QA-296, QA-298, QA-300, start_plant), gemini 0.6.26.

## [1.1.118] - 2026-11-05

- QA-291: live `agent.usage` event per nested agent session (tokens, cost, steps, start time).
- QA-270: the design report splits heating into brine heat, heat-pump electricity and backup.
- geomind main HEAD (0.4.129+), gemini dev HEAD (0.6.25: QA-285, QA-282, QA-214).

## [1.1.117] - 2026-11-05

- QA-231 (QA-144, QA-277): a run's usage only rises during the run and ends equal to the per-agent
  total of `/agents`.
- QA-274: chat sensitivity and uncertainty studies get a result each, so the Report offers them.
- QA-215: agent study results carry the saved plant version of their design; a design result of
  the same design and case version is not recorded twice.
- QA-220: the run log has `waits` (user wait per answered card) and `wait` on the gated call.
- geomind main HEAD (0.4.125+, QA-199, QA-265, QA-196, QA-168, QA-283).

## [1.1.116] - 2026-11-05

- QA-264: a run a restart left `waiting` on a request that already has the user's decision (the
  run had gone on past it) resumes from its log when that request is answered again, instead of
  `409 answered already`.

## [1.1.115] - 2026-11-05

- QA-264: a run a restart stopped after the user's decision asks the same request again; its
  answer is taken instead of `409 answered already` (a decision counts only when it is newer
  than the newest ask of that request).

## [1.1.114] - 2026-11-05

- QA-242: a run that the user stopped at its step limit and that answered from what it had is
  `done` with no error (geomind ends it as failed with `step_limit`).

## [1.1.113] - 2026-11-05

- QA-255: `POST /workspace/projects` without `mcp` gives the project every enabled MCP server,
  so its agents get the connectors (open-meteo) the admin switched on; `mcp: []` keeps none.

## [1.1.112] - 2026-11-05

- QA-252: `GEOMIND_COMPARE_CONCURRENCY=3` and `GEOMIND_COMPARE_RETRIES=1` in every backend env
  file: a comparison designs its families side by side and gives a failed family one more try
  (unset, they ran one at a time with no retry). No contract change.

## [1.1.111] - 2026-11-05

- QA-241: a free plant's `structure` keeps the plant-level params (`dispatch`, `outages`,
  `backup`), as gemini writes them on a plant without a class; the Plant page no longer shows
  them missing and a save keeps them.
- QA-244: `doublets` of a result whose plant has no class size counts its `Doublet` modules (a
  superstructure's `d0`, `d1`: 2).
- QA-249 (additive): every run of `GET /assistant/runs` has `prompt`, the user's message that
  started it.

## [1.1.110] - 2026-11-05

- QA-237: an assistant run no longer saves the designs it builds, changes or simulates as plant
  versions; the project plant changes only on an explicit save (Plant page) or adopt (Results).
  Reverses 1.1.82 (QA-092).
- QA-239 (additive): every result (list and detail) has `feasible`, true when no check failed or
  was not assessed, so a ranking leaves out a heating-only plant on a case that needs cooling.

## [1.1.109] - 2026-11-05

- QA-223: a `simulate` with `changes`, `start` or `end` (a what-if) never becomes the run's result
  row; the newest plain simulate does.
- QA-213: a result capacity with no peak carries gemini's `reason` (was always `null`).

## [1.1.108] - 2026-11-05

- QA-217: `GET /assistant/runs/{id}/agents` keeps each run's events in memory (64 runs) and
  reads only the events newer than the last read; the sessions are worked out again only when
  new events came. Postgres pool 20 + 20 overflow (was 5 + 10) in every env file. No contract
  change.

## [1.1.107] - 2026-11-05

- geomind 0.4.108 from the local clone (with 0.4.107 of hotfix-python, QA-168, QA-186): the
  project lead reads the project's plant versions and studies first, so a report request on a
  project with results goes to analysis and explanation, not a redesign (QA-167). No contract
  change.

## [1.1.106] - 2026-11-05

- geomind 0.4.106 from the local clone (with 0.4.103-0.4.105 of hotfix-python): after a worker
  restart a nested run goes on from its last step and a finished team mate keeps its answer
  (QA-176, QA-188); no nested run stays `running` (QA-184). `GEOMIND_TEAM_SIZE` (8 in prod), the
  most sub-agents a lead runs at once, no default (QA-201); in every backend env file, which now
  hold the same variables. No contract change.

## [1.1.105] - 2026-11-05

- `kombu>=5.6,<5.7` in `requirements.txt`: kombu 5.7.0 needs redis 6 and broke every image build
  without a layer cache. Ships geomind from the local clone (0.4.102: QA-162, QA-165). No contract
  change.

## [1.1.104] - 2026-11-05

- Hotfix deploy builds from local code (Sahand): `scripts/hotfix_deploy.sh` checks that the
  gemini (`dev`) and geomind (`main`) clones are committed and pushed, takes their `HEAD` with
  `git archive`, and `Dockerfile.hotfix` builds and installs both packages in the image over the
  released pins. No GitHub release and no separate wheel (`.tmp/hotfix-wheels` is no longer
  read). No contract change.

## [1.1.103] - 2026-11-05

- QA-148, QA-149: gemini 0.6.17 (local wheel): no TypeError on a non-port `inlets` entry, a
  closed loop without a first guess names what to set, inlet errors state the real problem.
  No contract change.

## [1.1.102] - 2026-11-05

- QA-147: geomind 0.4.98 (local wheel): read_stored and calculate read a dotted module key
  (`d0.esp`). No contract change.

## [1.1.101] - 2026-11-05

- QA-122: geomind 0.4.97 (local wheel): the agents read the project's plant versions and studies
  through `project_designs` and `plant_version` (served since 1.1.90). No contract change.

## [1.1.100] - 2026-11-05

- QA-145: geomind 0.4.96 (local wheel): the design engineers propose changes from their brief,
  the design lead builds once and applies all changes in one `patch_plant`. No contract change.

## [1.1.99] - 2026-11-05

- Speed measuring: `step.started` and `step.finished` carry `ts` (the event's own time) in the stream
  and in `/events`; each step of the run log has `ts` (when it started), added after `gd.runlog`.

## [1.1.98] - 2026-11-05

- QA-144: a running run's row (Runs and logs) showed 0 tokens and 0 USD. The live totals (`UsageTree`) now
  keep every nested run at any depth by run id and parent (a lead's instances are grandchildren of
  the root) and no longer need a root `usage` first; a run counts as the larger of its own totals
  and its children's sum, so ended children are not counted twice.

## [1.1.97] - 2026-11-05

- geomind 0.4.95 and gemini 0.6.16 as local wheels. gemini 0.6.16: QA-128 (carbon price only on
  the plant's own CO2e, not again on grid electricity). geomind 0.4.92: QA-140 (the case lead
  always splits into 2-4 geoscientists), search_knowledge/read_knowledge for sub-agents; 0.4.93:
  QA-143 (evaluate_module with design, identical failed call not run again); 0.4.94: QA-121
  (approval cards start with one sentence); 0.4.95: IMP-019 (one-value plant choices filled).

## [1.1.96] - 2026-11-05

- QA-135 (backend, option C by the user): when an assistant run finishes, its LAST successful plain
  `simulate` becomes one result: no study, named `simulation <design>`, with the case and plant
  versions it ran on when a saved version matches (else `null`), gemini's report and daily
  coverage computed from the run files geomind keeps. A run that simulates many times adds one row;
  the same run is never added twice. Study and Results no longer read "Out of date" right after
  a fresh chat simulation.

## [1.1.95] - 2026-11-05

- geomind 0.4.91 as a local wheel (gemini 0.6.15 kept). 0.4.90/0.4.91: IMP-025 parallel
  instances: a Team runs a list of {role, task} briefs at once (at most 4), each instance named
  `<Role> <Roman>` with `instance` on its events; the case lead runs several geoscientists, who
  read no file (the lead gives them the report text); the cost catalogue is
  `knowledge/data-economics.csv`/.md (was cost-sources.*).

## [1.1.94] - 2026-11-05

- IMP-025 (backend, part 2; contract with hotfix-python-IV and the frontend): parallel instances of
  one role ("Geoscientist I", "Geoscientist II") share `agent` and `parent` but each is its own
  nested run. The live text buffer, the live usage tree and tool problems are now keyed by the
  event's `run_id`, not by `agent`, so instances never mix. A buffered `text.delta` on reconnect
  carries `session` (that run id) and `instance` when it has one; `GET /assistant/runs/{id}/agents`
  gives each session `instance` (`null` outside a team of instances). geomind 0.4.90 puts
  `instance` on every event of an instance's run; the stream and `/events` pass it through.

## [1.1.93] - 2026-11-05

- IMP-025 (backend, part 1): the assistant's case and plant versions are saved one at a time, in
  the order geomind's events came. geomind tells the callbacks outside its save lock, so parallel
  agent instances saved at once: two saves could take the same number (the second was dropped) or
  an older case could land after a newer one.

## [1.1.92] - 2026-11-05

- geomind 0.4.89 as a local wheel (gemini 0.6.15 kept; 0.4.89 renames the handbook to handbook-design.md). 0.4.88: QA-131, `sensitivity` takes `values`
  (only the named drivers move); a chat sensitivity sets the user's ranges in the case, then
  runs gemini's sensitivity, never run_python.

## [1.1.91] - 2026-11-05

- QA-136: the report's "Agent log and tokens" writes tokens and cost as Runs and logs does
  (`14.8 M`, `625 K`, `0.46 USD`), no longer raw numbers.

## [1.1.90] - 2026-11-05

- QA-122: the agents' Workspace gets two read-only methods. `project_designs(project)` lists every
  plant version of the project (`version`, `name`, `note`, `by`, `created`, `latest`; oldest first)
  and every study (`id`, `name`, `kind`, `status`, `created`, `plant_version`, `case_version`,
  `settings`, `result` with `kpis` and `checks` as the results page lists them; newest first).
  `plant_version(project, n)` returns that saved plant as gemini wrote it, or `None`. Both are
  warmed before a run. Contract agreed with hotfix-python-IV; geomind reads them when present.

## [1.1.89] - 2026-11-05

- geomind 0.4.87 and gemini 0.6.15 as local wheels. 0.4.87: QA-129 (free plant doublet range in the skill), QA-132 (flow range on reservoir.liquid_flow). gemini 0.6.15: a doublet runs at most at its
  pump's nominal_flow (QA-130); a free plant takes a size.doublets range and the optimiser
  searches it (QA-129, gemini part). 0.4.86: QA-125 (`read_result` gives a
  series summary: peak and low with their day, active days; a module's operating days and
  energy), QA-124 (requirement values from `check_results`), QA-123 (with gemini 0.6.14 an
  exchanger rated in W/K is no longer reported as unused).

## [1.1.88] - 2026-11-05

- geomind 0.4.85 as a local wheel (with gemini 0.6.13). 0.4.85: QA-119 (reference depth moved alone is flagged), QA-120 (8 for 8 % refused). 0.4.84: read_rag by section (outline, section), knowledge hits name their section. 0.4.83: IMP-016 (a requirement failing
  three rounds stops the loop), IMP-017 (a passed design is optimised once), QA-097, QA-099
  (five significant digits), QA-114 (no version numbers to the user). 0.4.82: every tool documented in exactly one
  skill, descriptions one line plus the skill; IMP-014 (an engineer's own parts in refusals and
  issues), IMP-015 (a repeated error says to change the call), IMP-018 (plant writes checked
  before the approval), QA-116 (a denied tool is not asked again in the request).

## [1.1.87] - 2026-11-05

- QA-110 (backend part; the Case History UI is hotfix-front-III's): `GET
  /design/case/versions/{number}` opens a case version with its files and gemini's missing values;
  `POST /design/case/versions/{number}/restore` (`project`, `base`) saves it, content and files, as
  the next version, note "Restored version N". A case the assistant saves gets a note naming up
  to six changed paths and files ("Case set by the assistant: requirements.flow.max changed;
  ..."), not always "Case set by the assistant". Case and plant `Version` objects have `by`
  (`assistant` when the note says "by the assistant", else `user`), so Saved by can say Assistant.
- QA-102 (backend part): new activity rows of a saved case or plant version link to the version
  number (`link.id` "N"); older rows keep no id.
- QA-104 (backend part): a constraint with no value in a run with failed steps adds the largest
  failure group, module, first date and gemini's words, beside gemini's reason (page studies and
  every result read).
- Hotfix mode: ran test_case, test_versions, test_evaluate, tests/api/v1/plant, test_openapi,
  tests/scripts; `test_case_aware::test_validate_with_a_project_takes_the_values_from_its_case`
  fails before and after this change (gemini 0.6.13), not touched here.

## [1.1.86] - 2026-11-05

- geomind 0.4.81 and gemini 0.6.13 as local wheels: gemini 0.6.13 judges `unmet_share` of a run
  with failed steps undecided with the failed steps named (QA-104) and counts an electric
  boiler's heat as backup in the daily coverage (QA-107a); geomind: QA-104 (a requirement with
  no value names the failed steps), QA-105 (per-energy map all given or all open), IMP-012/IMP-013
  (evaluate_module and set_case fix slips of form, evaluate_module reads a design or a result),
  a tool's skill sent with its first result.

## [1.1.85] - 2026-11-05

- QA-106: Results, Constraints listed 12 rows for 10 case requirements. gemini checks each
  service's supply temperature itself under the same name as the case's rule
  (`heating_supply_temperature`, `cooling_supply_temperature`), so the name came twice, the
  service check took the case's limit, and the page's duplicate row keys drew a third row. Now the
  repeat is named `<module>.<name>.service`, titled "(service supply rule)", with gemini's own
  bound (heating at least, cooling at most the demand's supply temperature); a case rule in `°C`
  matches gemini's `degC`, so it shows its direction (`= 100 degC`). Computed on every result
  read, so existing results show it at once. Hotfix mode: only test_evaluate and
  test_no_comments ran.

## [1.1.84] - 2026-11-05

- geomind 0.4.80 as a local wheel (`.tmp/hotfix-wheels/`, with gemini 0.6.12). 0.4.80: the
  case lead takes economics from an assumptions document in Knowledge first (per-energy keys open
  when it gives none). 0.4.79: QA-091 (supply
  temperatures judged while running; heat/cold delivered over the year), QA-090 (the design lead
  stops chasing one failing requirement after three changes and reports it), QA-094 (network
  return temperatures are a design choice), QA-095 (knowledge row `co2-grid-organisers-2026`,
  300 g/kWh, recommended first for the hackathon cases).

## [1.1.83] - 2026-11-05

- Held batch: geomind 0.4.78 and gemini 0.6.12 as local wheels (`.tmp/hotfix-wheels/`):
  QA-074 (constant g, m/s2 and kg/m2), QA-079 (typed approve-all, approved items settled), QA-084
  (no subsidy recommended), QA-085 (country rows labelled), QA-086 (auto mode continues at the
  step limit), QA-088 (full runs in agent study records), gemini request 35 (ESP curve windows).

## [1.1.82] - 2026-11-05

- QA-092: the agent's design reaches the Plant page. Before, only `build_plant` saved a plant
  version, so a design the agents patched (`patch_plant`) and simulated stayed in the chat's
  `design/<name>` store and the Plant, Study and Results pages kept the old plant. Now a
  successful `patch_plant`, `merge_designs`, `set_ranges`, `size_plant` or `optimize` saves the
  design it stored, and `simulate` on a stored design saves that design, as the project's next
  plant version (equal content saves nothing). `union_designs` (an evolve superstructure) saves
  none. Hotfix mode: only test_versions and test_no_comments ran.

## [1.1.81] - 2026-11-05

- QA-088: when an agent study is recorded, each simulated run in its artifact's `runs` (geomind
  0.4.77: full gemini report, run, design reference) becomes a result row like a page study's,
  so agent studies appear in the Results tab with KPIs, capacities and constraints; coverage is
  computed on first read. Studies recorded before 0.4.77 have no `runs` and stay without results.
  Hotfix mode: only test_boundaries ran.

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
