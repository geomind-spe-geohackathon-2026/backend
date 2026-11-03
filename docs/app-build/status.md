# App status

Updated 2026-11-02. `handover.md` says how to work on the app; this file says where it stands.

## Production

geomind.team runs from this laptop. Deploys go through the Deploy thread.

| Part | Sent to production | Pushed to main |
| --- | --- | --- |
| backend | 67e9884 (v1.1.5) | see `git log` |
| frontend | c32f3e6 (v1.1.17) | see `git log` |
| gemini | wheel 0.5.14 | wheel 0.5.14 |
| geomind | 0.4.21 wheel by URL | 0.4.21 wheel by URL |
| sandbox image | `gemini-sandbox:0.5.14` | `gemini-sandbox:0.5.14`, pulled from ghcr |

Backend and contract version 1.1.5 (`src/version.py`, `CHANGELOG.md`). Latest migration 0013.

The projects SPE GeoHackathon 2026 and Live tests b, c and d were moved with `scripts/projects.py`.

## Done

- Assistant on DeepSeek only, refused otherwise before a run starts.
- Report: simplified process diagram, full flowsheet in the appendix on a landscape page, compact PDF within four pages.
- Modules merge in the diagram only when type, connections and settings are equal.
- Failed chat: readable stop, and the studies the run recorded. A chat on an incomplete case says so.
- gemini 0.5.4: all numbers of the competition studies equal 0.5.3 (3,020 compared), `hackathon.py` output identical.
- gemini 0.5.5: all numbers of the competition studies equal 0.5.4 (18,121 compared, coverage included).
- Phone width: no page scrolls sideways on 13 routes, wide tables scroll in their card with a fade.
- Compare: designs only, labels clear of each other, check text says all passed only when all were assessed.
- Range hints in the parameter form, for every module of a class.
- A run that ended after a failed tool stays `done`: geomind's status is what happened, and the chat shows the failure with the panel's count.
- A new doublet takes the values of the first one, as a gemini study does.
- Golden path: refusal on an incomplete case, then a saved profile that lands in the case.
- The assistant reads a project's uploaded files through `Workspace.files` and `Workspace.file` (geomind 0.4.4 and later).
- A study can run on a chosen plant version (`plant_version` in `POST /design/study`), so two designs of one project can be studied side by side.
- Assistant text streams over a WebSocket with SSE as a fallback; the chat shows it live at a natural pace.

## Context window

`GEOMIND_CONTEXT_WINDOW=128000` is our cost choice, not a fact of the model: DeepSeek v4.1 flash on Relace reports 1,048,576 tokens. geomind compacts at a share of this window, so the lower number keeps the context, and the cost of each call, as they were before 0.4.2 made the window a setting. Production has the same line.

## Compare loop

geomind 0.4.6 designs each plant family on its own, verifies and ranks them. The chat state gains `design.alternatives` and `design.comparison`, and a run can stop with `no_alternatives` or `no_verified`; the backend passes both through unchanged. `GEOMIND_COMPARE_CONCURRENCY`, `GEOMIND_COMPARE_RETRIES` and `GEOMIND_GEMINI_THREADS` are unset here and on production, so families run one at a time with no retry. A family that stops gives the tool error `nested_stopped` with its reason.

## Memory

`MALLOC_ARENA_MAX=2` is set in the image and the example env files. gemini runs studies on worker threads, and glibc's per-thread arenas grew one process to about 3.5 GB; with two arenas it stays at 1.0 to 1.7 GB (measured by geomind, 2026-11-03).

## Units

Results, summary and report read gemini's display units through `report.to_dict()` and the study results' `to_dict()`. `daily_coverage` and `compare` have no `units` argument, so there is nothing further to pass. The app still converts two things itself, which gemini's table does not cover: W/K to MW/K (`evaluate.readable`, thermal conductance is not in `DISPLAY_UNITS`) and MWh to GWh in report text, a choice of wording. A request for the first is in `gemini-requests.md`.

## Next geomind release (0.4.22, on gemini 0.6.1)

Ready in the backend: the workspace has `rag`, `mcp`, `files`, `file`, `knowledge_*` and `memory`, and passes a sandbox only to a geomind that takes one. At the release, in one change:

- pin geomind 0.4.22 and gemini 0.6.1 by URL and sha256; the sandbox image is no longer used;
- env: drop `GEOMIND_MODEL` and `GEOMIND_CHEAP_MODEL`; add one `GEOMIND_<ROLE>_MODEL` per agent, all `deepseek/deepseek-v4.1-flash-1017` (ANALYSISLEAD, CASELEAD, COORDINATOR, DESIGNLEAD, ECONOMIST, EXPLAINER, GEOSCIENTIST, REVIEWER, SUMMARIZER, PROCESSENGINEER, INTEGRATIONENGINEER, RESERVOIRENGINEER, WELLENGINEER, ENERGYSYSTEMSENGINEER, PROJECTLEAD, SUPPORTLEAD, CURATOR); add, from geomind's live runs: `GEOMIND_DESIGN_CONCURRENCY=3`, `GEOMIND_ENGINEER_MAX_STEPS=15`, `GEOMIND_EVOLVE_EVALUATIONS=60`, `GEOMIND_EVOLVE_POPULATION=12`, `GEOMIND_EVOLVE_SEED=0`, `GEOMIND_EVOLVE_POLISH=0`, `GEOMIND_MCP_TIMEOUT=30`, `GEOMIND_MAX_STEPS=30`, `GEOMIND_MAX_OUTPUT_TOKENS=16000`; keep `GEOMIND_CONTEXT_WINDOW=128000`, `GEOMIND_MEMORY_SIMILARITY=0.8` and production's retries (5 and 2; geomind's live tests used 3 and 0.5, Sahand decides); `GEOMIND_KNOWLEDGE_DIR` and `GEOMIND_MCP_SERVERS` are for geomind's command line only; `GEOMIND_PROVIDER=deepseek` instead of `relace/fp4`, so OpenRouter uses DeepSeek's own provider and its prompt cache (geomind measured about a third of the cost for the case team); production was set to `relace/fp4` on Sahand's word, so he confirms the switch;
- after the deploy, re-seed the cost catalogue with geomind dev's newer `data/knowledge/cost-sources.csv` (133 rows): `python -m scripts.knowledge add cost-sources.csv --by <admin email>` replaces the shared document of that name;
- frontend: `tool.started`/`tool.finished` carry `mcp` (was `connector`), and the tools are named `rag_search`, `rag_read`, `search_knowledge` and `<server>__<tool>`.

## Open

- The cost catalogue (`cost-sources.csv` from geomind c1aa8ea) is a shared Knowledge document on production since 2026-11-03.


- Wide report tables are not checked by eye on real data at phone width after the last deploy.
- Compare labels are tested, not checked by eye on a real chart of many designs.
- Whether Fatemeh Chitsaz's commit identity should also apply to the `ux/frontend` clone.
- The WebSocket works on production for a finished run (replay, resume, refused token). A running run has not been seen there under the no-token order.
- Study and document progress stay on polling, which is enough for them.
- Budget caps are not retested on DeepSeek, and the two live checks were skipped under the no-token order.

## Requests

- gemini: `gemini-requests.md`, among them ranges of generated modules and thermal conductance in the display table.
- geomind: `requests.md`, among them the crash at `loops/design.py:293`, the Anthropic default models, and context windows for other models. These wait for 0.4.2.
