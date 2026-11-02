# Design reports and studies

## Studies

`design/study` runs a gemini study as a Celery task (`design.study.run`, job id = study id).
`src/core/gemini/study.py` wraps gemini: `kinds()` (the `method` values, all sharing
`Study.schema()`), `missing_inputs()` (`Study.check()` plus `Case.from_dict`; a value
gemini finds unset is "missing", anything else is `case_invalid`, `plant_invalid` or
`validation_failed`) and `run()`. The case and plant come from the latest saved versions;
case files are read from MinIO. A study with missing inputs is created `blocked` and is
started later with `POST /design/study/{id}/start`.

gemini has no progress callback or cancel check for studies, so progress is `0/1` until the
end. Cancel sets the row to `cancelled`, sets the Redis flag and revokes the task with
terminate. The worker never overwrites a study that is no longer `running`.

## Results

One result per study: `summary` (KPIs, check counts) for lists and `content` (capacities,
constraints, gemini's report, run record and final design) for detail. `coverage` is `null`
until gemini publishes daily coverage by source; `series` is empty until gemini publishes
edge series. Compare maps the `pareto` flags of `gm.evaluate.compare` to result ids.

## Reports

`POST /reporting/design/preview` builds Markdown sections from a result; `export` returns
the same Markdown as `md` or `pdf` and writes an activity row with `link_route` `report`.
Costs show their source (case and plant version) next to each number; a figure gemini
cannot give says `missing`.

PDF library: **fpdf2**. It is pure Python, small (needs only Pillow and fontTools), has
tables built in, and needs no system packages, unlike WeasyPrint (Pango) or wkhtmltopdf.
`reporting/design/pdf.py` draws headings, tables, code, bullets and paragraphs from the
Markdown. It uses the built-in Helvetica font, so characters outside Latin-1 print as `?`.
