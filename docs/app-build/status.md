# App status

Updated 2026-11-02. `handover.md` says how to work on the app; this file says where it stands.

## Production

geomind.team runs from this laptop. Deploys go through the hosting thread.

| Part | Sent to production | Pushed to main |
| --- | --- | --- |
| backend | 5ce532c | see `git log` |
| frontend | ffd7673 | see `git log` |
| gemini | wheel 0.5.5 | wheel 0.5.5 |
| geomind | wheel 0.4.3 in `vendor/` | wheel 0.4.3 |
| sandbox image | `gemini-sandbox:0.5.5` | `gemini-sandbox:0.5.5`, pulled from ghcr |

Contract version 50. Latest migration 0009.

The projects SPE GeoHackathon 2026 and Live tests b, c and d were moved with `src.scripts.projects`.

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
- Assistant text streams over a WebSocket with SSE as a fallback; the chat shows it live at a natural pace.

## Context window

`GEOMIND_CONTEXT_WINDOW=128000` is our cost choice, not a fact of the model: DeepSeek v4.1 flash on Relace reports 1,048,576 tokens. geomind compacts at a share of this window, so the lower number keeps the context, and the cost of each call, as they were before 0.4.2 made the window a setting. Production has the same line.

## Units

Results, summary and report read gemini's display units through `report.to_dict()` and the study results' `to_dict()`. `daily_coverage` and `compare` have no `units` argument, so there is nothing further to pass. The app still converts two things itself, which gemini's table does not cover: W/K to MW/K (`evaluate.readable`, thermal conductance is not in `DISPLAY_UNITS`) and MWh to GWh in report text, a choice of wording. A request for the first is in `gemini-requests.md`.

## Open

- Wide report tables are not checked by eye on real data at phone width after the last deploy.
- Compare labels are tested, not checked by eye on a real chart of many designs.
- Whether Fatemeh Chitsaz's commit identity should also apply to the `ux/frontend` clone.
- The WebSocket works on production for a finished run (replay, resume, refused token). A running run has not been seen there under the no-token order.
- Study and document progress stay on polling, which is enough for them.
- Budget caps are not retested on DeepSeek, and the two live checks were skipped under the no-token order.

## Requests

- gemini: `gemini-requests.md`, among them ranges of generated modules and thermal conductance in the display table.
- geomind: `requests.md`, among them the crash at `loops/design.py:293`, the Anthropic default models, and context windows for other models. These wait for 0.4.2.
