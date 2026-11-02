# Inventory: Geomind clickable mockup

Source: `/Users/sahand/Desktop/geomind-spe-geohackathon-2026/docs/ui-mockup.html` (836 lines, single file, inline CSS and JS, no build). Read-only; not edited.
Screenshots: `/Users/sahand/Desktop/geomind-spe-geohackathon-2026/frontend/.tmp/build/mockup/` (43 PNG). Capture script: `/Users/sahand/Desktop/geomind-spe-geohackathon-2026/frontend/.tmp/build/capture.mjs`.

## 0. How the mockup is built

- Hash routing. `route()` reads `location.hash`, `render()` toggles the `.view` sections, the top bar, the project sidebar and the breadcrumb.
- Three levels (`LEVEL` map):
  - Level 0: sign in. No chrome.
  - Level 1: projects, account, users. Top bar only.
  - Level 2: everything else. Top bar, project sidebar and the view. Requires `state.project`.
- Global state is in memory only: `state.signed`, `state.project`. A reload returns to sign in.
- Each view can carry a `data-note` attribute. A yellow note box shows the note when the "Show the yellow notes" checkbox is on. The notes are the design rationale for each screen; they are part of the mockup, not product UI.
- All numbers are examples. The page header says the demand curves are the official 2027 inputs.
- Sample data is hard-coded in HTML and JS (`DATA`, `projects`, `MODS`, `STEPS`). Nothing comes from a backend.

## 1. Screens and routes

Light screenshots are numbered in the order of the user flow.

| # | Screen | Route (hash) | Level | Screenshot (light) | Screenshot (dark) | Screenshot (phone) |
|---|---|---|---|---|---|---|
| 1 | Sign in | `#signin` (also the fallback for any unknown hash, and for any route while signed out) | 0 | `00-signin.png` | `dark/00-signin.png` | `mobile/00-signin.png` |
| 2 | Projects home | `#projects` | 1 | `01-projects.png` | `dark/projects.png` | |
| 3 | Account | `#account` | 1 | `02-account.png` | `dark/account.png` | |
| 4 | Users (admin) | `#users` | 1 | `03-users.png` | `dark/users.png` | |
| 5 | Project overview | `#overview` | 2 | `04-overview.png` | `dark/overview.png` | `mobile/overview.png` |
| 6 | Assistant chat | `#chat` | 2 | `05-chat.png` | `dark/chat.png` | `mobile/chat.png` |
| 7 | Runs and logs | `#runs` | 2 | `06-runs.png` | `dark/runs.png` | |
| 8 | Run log | `#runlog` | 2 | `07-run-log.png` | `dark/runlog.png` | |
| 9 | 1 Problem | `#problem` | 2 | `08-1-problem.png` | `dark/problem.png` | |
| 10 | 2 Plant | `#plant` | 2 | `09-2-plant.png` | `dark/plant.png` | `mobile/plant.png` |
| 11 | 3 Study | `#study` | 2 | `10-3-study.png` | `dark/study.png` | |
| 12 | 4 Results | `#results` | 2 | `11-4-results.png` | `dark/results.png` | `mobile/results.png` |
| 13 | Report | `#report` | 2 | `12-report.png` | `dark/report.png` | |
| 14 | Documents | `#documents` | 2 | `13-documents.png` | `dark/documents.png` | |
| 15 | Project settings | `#settings` | 2 | `14-project-settings.png` | `dark/settings.png` | |

That is 15 screens. Level 2 routes fall back to `#projects` when no project is open. Signed-in users landing on `#signin` are sent to `#projects`.

Extra states captured (not separate screens):

- `01b-user-menu.png`: avatar menu open on projects.
- `01c-new-project-dialog.png`: "New project" modal.
- `05b-chat-after-approve.png`: chat after approving the uncertainty study.
- `08b-problem-economics-tab.png`: Problem, Economics tab (gas price and discount rate missing).
- `09b-plant-esp-selected.png`: Plant, ESP module selected in the flowsheet.
- `09c-plant-history-tab.png`: Plant, History tab.
- `11b-results-compare-tab.png`: Results, Compare tab.
- `14b-project-settings-delete-confirm.png`: delete confirmation.

Screenshot count: 43 total = 23 light (15 screens + 8 extra states, numbered `00` to `14b`), 15 dark (all screens), 5 phone (signin, overview, chat, plant, results). Dark uses Playwright `colorScheme: dark`, which exercises the `prefers-color-scheme` branch.

Fonts: Google Fonts (IBM Plex) is blocked in the sandbox, so every screenshot uses the system fallback, not IBM Plex. Layout is otherwise representative.

## 2. Components, data and interactions per screen

### 2.1 Sign in (`#v-signin`, level 0)

- Components: brand (logo dot and "Geomind"), tagline, Email input (prefilled `fatemeh@team.example`), Password input (prefilled `example-password`), "Sign in" primary button, text "Forgot your password? Ask an admin to reset it."
- Data: none. The prefilled values are fake.
- Interactions:
  - Submit (button or Enter): sets `state.signed = true`, goes to `#projects`. No credential check; any input works.
  - Note: "No public sign up: an admin creates users."

### 2.2 Projects home (`#v-projects`, level 1)

- Components: heading "Your projects", subtitle, search input (`#psearch`), "Import zip" button (no handler), a grid of project cards, dashed "+ New project" card.
- Data: `projects` array of 3 items:
  - "Delft heating + cooling", owner Sahand, updated today, progress `d d w d d` (Problem, Plant, Study, Results, Report), "3 chats · 32 runs · 1 running".
  - "Example doublet", owner Fatemeh, Oct 31, progress `d d . . .`, "1 chat · 4 runs".
  - "Rotterdam district heat", owner Sahand, Oct 28, progress `w . . . .`, "problem incomplete".
- Interactions:
  - Typing in search filters cards by name (case-insensitive, live).
  - Click a card: sets `state.project` to that name and goes to `#overview`.
  - "+ New project": opens the New project dialog.
- Progress bar: 5 segments; green = done, amber = in progress, grey = not started.

### 2.3 New project dialog (modal, opened from projects)

- Components: "New project" heading, Name input (default "Utrecht campus"), radio group "Start from": empty problem (default), copy of another project's problem, project zip. Cancel and Create buttons.
- Interactions:
  - Create: prepends a card (owner hard-coded "Fatemeh", "just now", progress all grey, "empty · start with the problem"), sets the project, toasts "Project created", goes to `#overview`. Empty name becomes "Untitled project". The radio choice has no effect.
  - Cancel: closes.

### 2.4 User menu (avatar, top bar, all signed-in levels)

- Components: avatar "FN" button (`#avatar`), dropdown with "Fatemeh N." / admin / email, "Account and password", "Users (admin)", "Theme: system" (toggle), "Sign out".
- Interactions:
  - Avatar: toggles menu. Clicking outside closes it. A route change closes it.
  - Account and password: `#account`. Users (admin): `#users`. Not role-gated.
  - Theme button: cycles system, light, dark. Writes `data-theme` on `<html>`; "system" removes it. The menu stays open after a theme click.
  - Sign out: clears `signed` and `project`, goes to `#signin`.

### 2.5 Account (`#v-account`, level 1)

- Components: read-only key/value card (Name Fatemeh N., Email, Role admin); "Change password" form (Current, New, submit button, "You will be signed out everywhere.").
- Data: static.
- Interactions: submit shows toast "Password changed. Please sign in again.", then after 1.2 s signs out to `#signin`. No validation.

### 2.6 Users (`#v-users`, level 1, admin)

- Components: heading and "Add user" primary button, table with Name, Email, Role (select), Status (chip), action button.
- Data: 3 rows: Sahand N. (admin, active), Fatemeh N. (admin, active, no action button), Guest reviewer (member, active).
- Interactions:
  - Add user: appends an editable row (Name, Email, role select, "new" chip, "Create" button). Create only toasts "User created"; the row is not saved.
  - Deactivate: changes the chip to "inactive" and the button to "Activate". Clicking "Activate" sets the chip back to inactive, so the mockup cannot re-activate a user.
  - Role selects: no handler, value changes locally only.

### 2.7 Project overview (`#v-overview`, level 2)

- Components:
  - Heading "Delft heating + cooling" (hard-coded) and subtitle "Deep geothermal heating at 100 °C and cooling at 20 °C for a district, 365 days a year."
  - Ask box: input, "Ask" button.
  - "Design progress" stepper, five cards: Problem ("2 missing", warn), Plant ("valid · v7", ok), Study ("1 running", info), Results ("3 designs", ok), Report ("draft", off). Each card opens its page.
  - "Recent chats" card: three items (09:41 "Design heating + cooling" running; Yesterday "Why two doublets?"; Oct 31 "Gas price sensitivity"). "All chats" link.
  - "Activity" card: 09:44 designer agent started study "Min LCOH, 1–3 doublets"; 09:40 Sahand saved plant v7 "bigger chiller"; Nov 1 Case v4 cooling demand file replaced.
- Interactions:
  - Ask: empty text still navigates to chat. Non-empty text becomes a user message in chat, and the chat input is cleared. Navigates to `#chat`.
  - Stepper cards and chat links navigate.

### 2.8 Assistant chat (`#v-chat`, level 2)

Three columns: chat list (190 px), conversation (flexible), run panel (250 px).

- Chat list: "+ New chat" button, three items (the first is active, "running · 09:41"). Clicking an item moves the active style only; the message list does not change.
- Conversation:
  - Fixed transcript: user message ("Design a geothermal system for this project's heating and cooling demand…"). Coordinator bubble with a tool row `read_case` (done, 0.2 s), a delegated "designer" group with `size_plant` (done, 3.1 s), `simulate` (done, 4.8 s), `optimize` (running, 38/120). Prose answer ends with a link "See it in Results".
  - Approval card (warn): "Run an uncertainty study: 200 simulations, about 3 minutes, about $0.30." Approve and Deny.
  - Input bar: text input, "Send" submit button, "Cancel run" button.
- Run panel:
  - Stats card: "Run #32", state chip "running", tokens "41.2k in · 3.1k out", cost "$0.18".
  - Agents tree: coordinator, designer (optimize …), verifier (waiting), economist (waiting).
  - "What it knows" key/values: Peak heat 30.0 MW, Peak cool 10.0 MW, Source 330 d/yr, Gas price "not set" (missing style). "Edit" link to Problem.
  - "Open full log →" to `#runlog`.
- Interactions:
  - Send or Enter: appends the user bubble, and after 700 ms appends a fixed "analyst" reply (a tool row `read_result` and a canned paragraph saying the real agent would stream here). The reply does not depend on what was typed.
  - Approve: replaces the approval card with a green "approved" row, sets the uncertainty row in Study to running at 8/200 (4%), toasts "Study started".
  - Deny: replaces the card with a grey "denied" row. Study stays "waiting" (not updated).
  - Cancel run: run chip becomes grey "cancelled", toast "Run cancelled". Nothing else stops.
  - New chat: replaces the transcript with "New chat. Ask anything about this project." Toast "New chat".
  - Run pill in the top bar (Delft project only, "1 run active · 02:14") goes to `#chat`.

### 2.9 Runs and logs (`#v-runs`, level 2)

- Components: heading, subtitle, header total "Project total: 31 runs · 2.1M tokens · $6.40", table with Run, Chat, Agents, Status, Tokens, Cost, Started.
- Data (4 rows):
  - #32, Design heating + cooling, coordinator and designer, running, 44k, $0.18, 09:41.
  - #31, same chat, 5 agents, done, 196k, $0.71, 09:12.
  - #30, Why two doublets?, analyst, done, 18k, $0.05, yesterday.
  - #29, Gas price sensitivity, economist, stopped, 9k, $0.03, Oct 31.
- Interactions: any row (`tr.click`) opens `#runlog`. Rows are not individually linked; all go to run #31.

### 2.10 Run log (`#v-runlog`, level 2)

- Components:
  - Header: "← All runs" link, heading "Run #31 · Design heating + cooling", meta line "done · 6 m 12 s · 184k in · 12.4k out · $0.71", buttons "Export JSON" and "Export Markdown".
  - Left: step list, 9 entries (LLM call and tool call per step, sub-steps indented). Each shows tokens.
  - Right: panel for the selected LLM call (system prompt in a collapsible `<details>`, answer), and a panel for the tool call (input, output, status chip "ok").
  - Summary table by agent: coordinator 2 steps 4.3k in 0.6k out $0.02; designer 9 steps 121k 7.9k $0.48; verifier, economist, explainer 5 steps 58k 3.9k $0.21.
- Data (`STEPS`, 5 entries shown in the list):
  - coordinator step 1: delegate to designer.
  - designer step 1: size_plant (2 doublets, 2500 m; heat 31.2 MW, cooling 9.1 MW, violation cooling_short_12_days).
  - designer step 2: simulate (365 days, 35 backup days).
  - verifier step 1: evaluate (5 of 6 pass, pump efficiency not assessed).
  - economist step 1: economics (LCOH 41.8 €/MWh, gas price missing).
- Interactions:
  - Clicking a step selects it and updates the panels. The first step shows in the detail panel on load (step index 1, the designer).
  - "← All runs" goes to `#runs`. Export JSON and Export Markdown only toast "Exported run-31.json" or ".md". No file is produced.
- Note: the step list shows 5 entries, while the summary says 16 calls. The list is a sample.

### 2.11 1 Problem (`#v-problem`, level 2)

- Header: "1 · Problem", subtitle, "Case v4" label, "Save version" (toast "Case v5 saved").
- Blocker card (warn): "2 values missing · gas price and discount rate. Cost results and the gas sensitivity study cannot run without them." "Fill them in" switches to the Economics tab.
- Tabs (pills): Demand (default), Site and reservoir, Constraints, Economics.
- Demand pane:
  - Chart card "Daily demand 2027": SVG line chart of 365 daily values, heating (heat colour) and cooling (cold colour), y axis 0 to 30 MW, x labels Jan, Apr, Jul, Oct. Legend shows heating 111.7 GWh, peak 30.0 MW, and cooling 23.7 GWh, peak 10.0 MW. Both totals match the series.
  - Files card: two "loaded" chips (`heating_demand_daily_2027.csv`, `cooling_demand_daily_2027.csv`), "Replace a file" (no handler), heating supply temperature 100 °C, cooling supply temperature 20 °C, network return temperatures select (Design choice / Fixed values, no handler).
- Site and reservoir pane (six fields, no handlers): reservoir pressure 245 bar, geothermal gradient 31 K/km, surface temperature 10 °C, well depth select (Design choice / Fixed), brine salinity 120 g/L, gas in brine 0.6 Nm³/m³.
- Constraints pane: table of six constraints (flow 50 to 300 m³/h per doublet; brine cooled at most 40 K; source available 330 days/yr; demand covered 365 days/yr; injection volume balance ±0 %; pump efficiency "from case"). "Add constraint" (no handler).
- Economics pane (six fields):
  - Electricity price 0.11 €/kWh (source CBS 2025).
  - Gas price, missing, warn border, placeholder "required", €/MWh.
  - Discount rate, missing, warn border, placeholder "required", %.
  - Lifetime 30 years.
  - CO₂ price 85 €/t (source EU ETS 2025 average).
  - Price year 2025.
- Interactions: tab switching only. Inputs have no validation and no save. The missing-value warnings never clear, even if the fields are filled.

### 2.12 2 Plant (`#v-plant`, level 2)

- Header: "2 · Plant", subtitle, "valid" chip, "v7 · saved by Sahand 09:40", "Start from template" (no handler), "Save version" (toast "Plant v8 saved").
- Tabs: Flowsheet (default), History.
- Flowsheet pane, three columns (150 px palette, flexible SVG, 230 px inspector):
  - Palette: eight non-functional items with coloured swatches (Doublet, ESP pump, Heat exchanger, Heat pump, Absorption chiller, Storage tank, Gas boiler, Demand). The items show a grab cursor but have no drag handlers.
  - SVG flowsheet (viewBox 640×330, min width 560 px, in a horizontal scroll): nodes `doublets` (2 × 2500 m), `injection`, `esp` (180 m³/h), `hx` (22 MW, selected by default), `heatpump` (COP 3.4), `chiller` (10 MW), `backup` (gas), `grid` (power), `heatnet` (100 °C), `coolnet` (20 °C). Pipes are coloured by stream: brine (dashed return), heating water, chilled water, gas, power.
  - Inspector: title (from the selected module) and a form built from `MODS`.
- Selecting a module (click on the SVG node) highlights it and rebuilds the form. Form fields and missing-value markers come from `MODS`:
  - doublets: count 2, depth 2500 m, "Design choice" (depth and count).
  - injection: injection temperature (from hx), max wellhead pressure 40 bar.
  - esp: flow 180 m³/h, efficiency missing, setting depth 450 m.
  - hx: duty 22 MW, approach 5 K, cost per kW missing.
  - heatpump: heating capacity 9 MW, supply 100 °C, COP 3.4.
  - chiller: cooling capacity 10 MW, supply 20 °C, COP 0.7.
  - backup: gas boiler capacity 32 MW, efficiency 92 %.
  - grid: price "from problem".
  - heatnet: supply 100 °C, return "design choice".
  - coolnet: supply 20 °C, return "design choice".
- Legend: brine, heating water, chilled water, gas, power.
- History pane: table v7 (Bigger chiller, Sahand, 09:40, current), v6 (Design B from run #31, designer agent, 09:18, Restore), v5 (Added backup boiler, Fatemeh, Nov 1, Restore). Restore buttons have no handler.
- Interactions: module selection, tab switch, Save version toast. The palette, Start from template and Restore do not work. Form inputs do not save.

### 2.13 3 Study (`#v-study`, level 2)

- Header: "3 · Study" and "New study" (toast "Pick a kind: size, optimise, uncertainty or sensitivity").
- Table of 4 studies:
  - Min LCOH, 1–3 doublets: optimise, designer agent, running, progress 38/120, bar 32 %, result "best 41.8 €/MWh".
  - Reservoir uncertainty: uncertainty, designer agent, waiting, "waiting for approval in chat", no result. Row id `uncrow`, updated by Approve.
  - Two doublets, 2500 m: size, designer agent, done, 3 s, result "31.2 MW heat →" to Results.
  - Gas price ± 40 %: sensitivity, economist agent, blocked, not started, "gas price missing →" to Problem.
- Interactions: result links navigate. Approve in chat changes the uncertainty row to running 8/200. Denying does not change it.

### 2.14 4 Results (`#v-results`, level 2)

- Header: "4 · Results" and the primary "Make report from Design B" button (to `#report`).
- Tabs: Design B · 2 doublets + chiller (default), Design A · 1 doublet + boiler, Compare.
- Design B pane:
  - Four KPI cards: heat capacity 31.2 MW, cooling capacity 10.4 MW, LCOH 41.8 €/MWh, CO₂ 19.6 kt/yr.
  - "Days covered, 2027" grid: 365 cells, one per day. Geothermal (ok green), backup during shutdown (grey). Shutdown days are 120 to 136 and 280 to 297 (0-based), so 35 days total. Caption: "Grey cells are the 35 days the source is down; the backup covers them."
  - "Constraints" card: "5 of 6 pass" chip, table of six checks (five pass; pump efficiency "not assessed").
- Design A pane: KPI cards only: heat 18.0 MW geo, boiler 14.0 MW, LCOH 38.9 €/MWh, CO₂ 27.4 kt/yr.
- Compare pane:
  - Pareto SVG: cost (LCOH, x axis 35 to 55) against CO₂ (y axis 10 to 30 kt/yr) for A (38.9, 27.4), B (41.8, 19.6, filled, larger), C (49.5, 15.1). Dashed line joins them. Caption "dashed line = best trade-offs".
  - Table: A · 1 doublet + boiler, 38.9, 27.4, 6/6; B (bold), 41.8, 19.6, 5/6; C · 3 doublets, 49.5, 15.1, 6/6.
- Interactions: tab switching. The make-report button navigates. No other handlers.

### 2.15 Report (`#v-report`, level 2)

- Header: "Report" and subtitle "Draft from Design B and run #31."
- Left: draft document. Title "Integrated deep geothermal heating and cooling, Delft". Sections: 1 Capacities (text), 2 Design (placeholder "Flowsheet of plant v7", not drawn), 3 Checks (5 of 6, pump efficiency not assessed), 4 Agent log (16 LLM calls, 184k in, 12.4k out, $0.71).
- Right: selects "Design" (B, A, C) and "Agent log from" (Run #31, Run #32). Four checkboxes (all checked): Capacities and design, Constraint checks, Costs and sources, Agent log and tokens. Buttons "Export PDF" (toast "report-design-b.pdf exported") and "Export Markdown" (toast "report-design-b.md exported").
- Interactions: the selects and checkboxes change nothing in the draft. Exports only toast.

### 2.16 Documents (`#v-documents`, level 2)

- Header: "Documents" with the subtitle "The assistant searches these and cites them." and "Upload" (no handler).
- Table: Hackathon challenge requirements.pdf (156 KB, searchable yes, Oct 29); Absorption chiller datasheet.pdf (2.1 MB, indexing, 09:30).
- Interactions: none beyond the static table.

### 2.17 Project settings (`#v-settings`, level 2)

- Components: Name input (value "Delft heating + cooling"), "Export zip" row (toast "delft-heating-cooling.zip exported"), "Delete project" danger row.
- Delete flow: "Delete project" reveals a confirm row "This cannot be undone." with "Yes, delete" (goes to `#projects` and toasts "Project deleted", but does not remove the project card) and "Keep it" (hides the row).
- Interactions: name field has no save. Delete does not remove the project from the list.

## 3. Global interactions

- Top bar: brand "Geomind" goes to `#projects`. Breadcrumbs: Projects, then project name, then section, then page. Each item is a link except the current page.
- Project sidebar (level 2 only): project name and "Switch project" (to `#projects`). Groups:
  - Overview.
  - Assistant: Chat, Runs and logs.
  - Design: 1 Problem (warn dot "2 values missing"), 2 Plant (ok dot "valid"), 3 Study (accent dot "running"), 4 Results (ok dot "ready"), Report.
  - Operation: Time series, Well performance, Integrity. All disabled, tagged "later".
  - Footer: Documents, Project settings.
- Sidebar and run pill: the pill shows only in the Delft project (`projects[0].name`). Opening any other project still shows the Delft overview content.
- Toasts: a dark pill at the bottom centre for 1.8 s. Many buttons only toast.
- Notes toggle: "Show the yellow notes" in the page header (on by default) shows or hides the note box for the current screen.
- Route guard: unknown hash goes to sign in. Level 2 without a project goes to projects. The URL hash is not corrected, so `#chat` can show the projects view (verified: URL stays `#chat`, visible view is `v-projects`).
- Responsive: under 1000 px, the chat columns stack, and the two- and three-column grids go to one column. Under 720 px, the sidebar becomes a horizontal scroll strip. Phone check at 390 px on results: no horizontal page overflow (0 px).

## 4. Design tokens

### 4.1 Colours (light `:root`, dark for `prefers-color-scheme: dark` and `[data-theme="dark"]`)

The dark values are the same tokens under `:root:not([data-theme="light"])` in the media query and under `:root[data-theme="dark"]`. Both are defined; they must be kept in sync.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#eef1f4` | `#0f151b` | page background |
| `--surface` | `#ffffff` | `#17202a` | cards, inputs, menus |
| `--sunken` | `#e7ebef` | `#0c1116` | sidebar, code blocks, hover, progress track |
| `--border` | `#d3dae1` | `#293643` | borders, dividers |
| `--fg` | `#17212b` | `#e2e8ee` | text; also the toast and active tab background |
| `--muted` | `#5b6977` | `#91a0ae` | secondary text, labels |
| `--accent` | `#0f6e84` | `#4fb3c9` | links, primary buttons, active nav, focus ring |
| `--accent-soft` | `#dbecf0` | `#15343d` | active nav, selected choice, user message bubble |
| `--on-accent` | `#ffffff` | `#0c1116` | text on accent |
| `--ok` | `#2f7d4a` | `#5cbf7d` | done, valid, geothermal coverage |
| `--warn` | `#a46700` | `#e2a742` | missing values, waiting, request border |
| `--bad` | `#b3362c` | `#ec7a6f` | blocked, stopped, delete |
| `--ok-soft` | `#e0f0e5` | `#163125` | ok chip background |
| `--warn-soft` | `#f7ebd2` | `#392c11` | warn chip, approval card |
| `--bad-soft` | `#f6dfdc` | `#3c1b18` | bad chip |
| `--note` | `#fff6d8` | `#2e2916` | yellow note box |
| `--note-fg` | `#5a4910` | `#ebdba2` | note text |
| `--shadow` | `0 10px 30px rgba(20,30,40,.18)` | `0 10px 30px rgba(0,0,0,.5)` | menu, dialog, toast |

Stream colours (used for the plant and the demand chart):

| Token | Light | Dark | Stream |
|---|---|---|---|
| `--hot` | `#d0542b` | `#ee7a50` | brine (geothermal water); also doublets and injection nodes |
| `--heat` | `#e0912f` | `#f0ab55` | heating water (100 °C); heat demand line |
| `--cold` | `#2f74c9` | `#6aa6ec` | chilled water (20 °C); cooling demand line |
| `--gas` | `#7c8a96` | `#9aa8b4` | gas (backup boiler) |
| `--power` | `#7a5bc0` | `#a78be6` | electricity (grid) |

Stream notes:

- Doublet and ESP are brine (`--hot`). Heat exchanger, heat pump and heating network are heating water (`--heat`). Absorption chiller and chiller are chilled water (`--cold`). Gas boiler and backup use `--gas`. Grid uses `--power`.
- Storage tank is coloured `--heat` in the palette, so it does not match its stream colour.

Light and dark ratio: the accent and the stream colours brighten for dark mode. Surfaces invert.

### 4.2 Typography

- Family: `"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif` (`--sans`). Mono: `"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace` (`--mono`). Both from Google Fonts (weights 400, 500, 600 for Sans; 400, 500 for Mono).
- Body 14 px, line height 1.45.
- h1 20 px, weight 600. h2 16 px, weight 600. h3 13 px, weight 600.
- `.label` 11 px, uppercase, letter-spacing .06em, muted, weight 500.
- `.mono` 12.5 px (tree, code, file names). `pre` 12 px, line height 1.5.
- Chip 11.5 px, weight 500. Pill 12 px. Table header 12 px, muted, weight 500. Tab 12.5 px. Small notes 12–13 px.
- Numbers use tabular figures (`font-variant-numeric: tabular-nums`).
- KPI value 22 px, weight 600; unit 12 px, muted.

### 4.3 Spacing

- Base unit is 2 to 4 px multiples. Common values: 4, 6, 8, 10, 12, 14, 16, 18, 22 px.
- Body side padding is `max(16px, env(safe-area-inset))`, block padding 16 px.
- Page header max-width 1280 px. Frame max-width 1280 px.
- Card body 12 px; card header padding 10 px 12 px; view padding 18 px; home padding 22 px.
- Grid gap 12 px; stepper gap 8 px; chat gap 14 px; run log gap 12 px.
- Inputs: padding 7 px 10 px. Buttons: 6 px 12 px. Table cells: 7 px 8 px.

### 4.4 Radii

- Frame 10 px. Dialog 10 px. Card, pcard, stepcard, choice, request, blocker, placeholder 8 px.
- Input, button, menu, tool row, pre, bar fill 6 px. Menu 8 px. Ask box and input bar 8 to 10 px.
- Pill, chip, tab, progress bar: 99 px.
- Logo and avatar: 50 % (circle). Swatch 2 px. Coverage cells 1 px.

### 4.5 Sizes and layout

- Frame min-height 740 px.
- Project sidebar 210 px.
- Chat columns 190 px, flexible, 250 px. Min height 610 px.
- Run log columns 240 px, flexible.
- Plant columns 150 px, flexible, 230 px.
- Dialog 460 px. Sign-in box 380 px. Account and settings 560 to 600 px. Home 1040 px.
- Project cards minimum 250 px wide, auto-fill.
- Stepper: five columns, two at 1000 px.
- Breakpoints: 1000 px (chat stacks, multi-column grids collapse to one), 720 px (sidebar becomes horizontal strip).
- Coverage grid: 73 columns (365 cells).

### 4.6 Elevation, motion and focus

- Shadow only on menu, dialog and toast.
- Focus ring: 2 px outline in `--accent`, offset 1 px (`:focus-visible`).
- Live dot pulses (1.4 s) and is disabled under `prefers-reduced-motion`.
- Hover: buttons get a muted border; nav and table rows get `--sunken`; project and stepper cards get an accent border.

### 4.7 Mode handling

- Theme: system by default; the menu cycles light, dark, system.
- Light is default. Dark applies from the `prefers-color-scheme` media query (guarded by `:root:not([data-theme="light"])`) or from `[data-theme="dark"]`.
- `color-scheme: dark` is set in dark mode, so native controls follow.
- Body background is always set explicitly (`--bg`).

## 5. User flow

Main path, with the mockup's own labels:

```
Sign in (#signin)
  -> Projects (#projects)
       -> open a project card (sets project, #overview)
            Overview (#overview)
              -> ask the assistant (ask box) -> Chat (#chat)
              -> or work through Design:
                 1 Problem (#problem) -> 2 Plant (#plant) -> 3 Study (#study)
                 -> 4 Results (#results) -> Report (#report)
              -> Runs and logs (#runs) -> Run log (#runlog)
              -> Documents (#documents), Project settings (#settings)
  -> Account (#account), Users (#users, admin) via the avatar menu
  -> Sign out (back to #signin)
```

Concrete steps in the chat flow, as the mockup plays them:

1. In chat, the coordinator reads the case, delegates to the designer, and the designer runs `size_plant`, `simulate` and `optimize`.
2. The assistant asks approval for an uncertainty study. Approve starts it in Study. Deny leaves Study waiting.
3. The answer points to Results. The run log (`#runlog`) shows each agent step with prompt, answer, tool input and output.
4. Results: pick a design and compare. "Make report from Design B" opens Report. Export only toasts.

Missing-value flow: Problem shows the blocker. "Fill them in" opens the Economics tab. Plant warns for a missing efficiency and missing cost per kW. Study marks the gas sensitivity blocked with a link back to Problem.

Creating a project: "+ New project" -> dialog -> Create -> overview of the new project (empty progress, "empty · start with the problem").

## 6. Open problems and observations in the mockup

These are things the mockup does or implies that may not match intent. Nothing was changed.

1. Overview heading and content are hard-coded to "Delft heating + cooling". Opening "Rotterdam district heat" or "Example doublet" changes only the sidebar name and the top-bar run pill logic; all content stays Delft.
2. Route guard does not rewrite the hash. With no project open, `#chat` (or any level 2 route) shows the projects view while the URL still reads `#chat`.
3. Users: "Activate" cannot reactivate. Clicking it sets the chip back to inactive.
4. Deny in chat does not change the Study row. The row stays "waiting for approval in chat".
5. Chat "Ask" from overview: any reply is the same canned analyst text, regardless of the question. The Send button does the same.
6. Cancel run changes only the chip to "cancelled". The run pill "1 run active · 02:14" is static and does not update.
7. Study says "best 41.8 €/MWh" for the optimise run, and Design B's LCOH is 41.8. But Design A has a lower LCOH (38.9) and passes 6 of 6 checks. Results and Study may disagree on what "best" means.
8. Run numbers do not agree: Chat run #32 shows 41.2k in tokens and Runs shows 44k for the same run.
9. Runs page says "31 runs", but Overview says the Delft project has "32 runs" and the table shows only four.
10. Run log summary sums to 16 calls; the step list shows 5 steps. Acceptable as a sample, but it is not the full log.
11. Gas boiler: plant v7 backup is 32 MW, Design A boiler is 14 MW. These are different designs, so this is likely fine, but the page does not say which plant version Design A uses.
12. The Report text says "Two doublets at 2500 m deliver 31.2 MW heat" while the Design B KPI says heat 31.2 MW and the Design B constraint says "5 of 6 pass". Consistent, but "Design" section placeholder is not drawn.
13. Storage tank palette item uses the heating colour, although no storage module exists in the flowsheet.
14. Plant "Demand" palette item uses the border colour (grey), not a stream colour.
15. Palette items show a grab cursor but cannot be dragged; the flowsheet is not editable beyond selecting a module.
16. Missing-value markers on Problem and Plant never clear. They do not respond to typing.
17. Project settings: "Yes, delete" navigates to Projects and toasts, but the project card stays in the list.
18. Users menu item and the Users route are not limited to admins in the mockup, even though the label says "admin only".
19. New project: the owner is always "Fatemeh", and the Start-from choice does nothing.
20. Sign-in accepts any password, and the page is prefilled with an email and password. It is a mockup; confirm these are not reused as real defaults.
21. Google Fonts IBM Plex is loaded from a CDN. Offline, the page falls back to the system font; screenshots reflect the fallback.
22. Four console errors were logged during capture: `net::ERR_FAILED` from the font requests, which the capture script aborts on purpose. Not a page error. The page raised no uncaught exceptions.
23. Stray `</output>` at line 509 of the HTML (inside the Plant palette). The HTML parser ignores it, so there is no visible effect, but it is invalid markup.
24. The theme menu stays open after a theme click, unlike other menu actions.
25. Dark mode is defined twice (media query and `[data-theme="dark"]`); the blocks must be kept in sync by hand.
26. The Plant page uses an inline `grid-template-columns` (150 px, flexible, 230 px) with `!important` in the media query to override it, so the layout depends on that override.
27. Chat "Send" and Enter both work; the text is not sent to any backend, and the "Cancel run" button is inside the form with `type="button"`.

## 7. Verified interactions (Playwright)

Checks run in the capture script. All of these passed after the correction noted:

- Open project card: goes to `#overview`.
- Ask from overview: goes to `#chat`; the user message is added and the canned analyst reply appears after 700 ms.
- Approve: removes the request card, sets the Study row to 8/200.
- Cancel run: run chip becomes "cancelled".
- New chat: resets the transcript.
- Run pill visible in the Delft project.
- Deactivate: chip becomes "inactive".
- Theme button: menu stays open; cycle reaches dark (`data-theme="dark"`) and returns to system (attribute removed).
- Password change: goes to `#signin` after 1.2 s.
- Chat with no project: visible view is the projects view, URL hash remains `#chat` (problem 2 above).
- Phone 390 px: no horizontal overflow on results.

Two checks failed on the first run because the expected values were wrong in the script, not in the mockup. The message count is 4 (not 5), and the URL hash is not rewritten. Both were corrected before the final run.
