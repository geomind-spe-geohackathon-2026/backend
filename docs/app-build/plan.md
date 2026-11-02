# Build plan

Target: gemini 0.5.0 (ae92de46, snapshot backend/.tmp/snap/gemini-0.5.0, installed in backend/.venv). geomind: code to the RunStore protocol; snapshot eeb80d9 now, refresh from origin main before Phase D and rerun the adapter tests. Contract: ../docs/contracts.md version 20.

Phase C tasks and ownership: as section 6 of the prompt, unchanged (C1 to C8).

Gemini gap decisions:
- Plant document check: Plant.from_dict + check(). No 501. Templates: gm.plants.names().
- Case section titles: derive from schema top-level properties, never a fixed list. Series: Case.from_dict(data, files=...) leaf.series.time/.si.
- Module title: describe()["type"]. Parameters from parameter_schema().
- Study kinds: gemini method enum, shared Study.schema(). Progress done 0/total 1 until end. Cancel: Celery revoke with terminate.
- Coverage: null; frontend shows "not available". No backend physics.
- Pareto: compare() flags mapped to ids.
- No plant migration: old documents fail with plant_invalid.

Geomind gap decisions:
- run.error.message from run.finished. Use astart/aresume in the worker; pass sandbox and permissions to Run.load.
- Budget per project is not available: use TokenBudget per run; report it.
- Chat artifacts implemented in the backend store and tested directly.
- Agent studies are not shown as study rows; requests list.

## Follow-ups for Phase D cleanup agent
- Progress: wire case state `incomplete` from gemini missing (C1 needs C2's validate).
- Import: check case content through gemini on project import.
- Delete MinIO objects (documents, case files, layout) on project delete.
- One `?project=` dependency in src/core/security/access.py; three copies now.
- Reconcile C1 document storage with C2 BlobStore.
- Upload size limit on case files.
- PDF report is a bug, not a request: embed a free Unicode font with Latin and Arabic-script coverage (Vazirmatn, or Noto Sans + Noto Sans Arabic; OFL; commit font files with the licence), register with fpdf2 add_font, enable set_text_shaping (uharfbuzz). Test: export a report whose project name is Persian and check the PDF text has no "?" substitutions. Do it after C4 merges.
- Reconcile C3's case_missing in src/core/gemini/study.py with C2's case.py. Study creation must not need MinIO when the case has no files.
