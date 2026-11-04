# Backend B4: Well performance

## Goal

The API for nodal analysis, injectivity analysis and pump performance with calibration.

## Context

- Follow the shared rules in `../docs/phases.md` (section "Rules for every phase") and the contracts in `../docs/contracts.md`.
- Needs B3. Read `../docs/feature-map.md`, domain `performance`, and the legacy entries PWL, INJ, ESP.
- **Add this phase's routes to `contracts.md` first** and tell the frontend.

## Layout

```
src/api/v1/performance/  nodal  injectivity  pump
```

## Steps

1. **nodal:** estimate the operating point of a production well (IPR/VLP) and compare what-if conditions.
2. **injectivity:** Hall integral and derivative over a time range; skin lines.
3. **pump:** pump against its manufacturer curve with measured points; calibrate the correction factors; save them as a new plant version.

Rules for all three:

- Calculations are gemini calls through `core/gemini`. Physics the legacy JavaScript did (head bar → m, `a × h + b`) moves into gemini, not here.
- Long calculations are Celery jobs with progress, timeout and a failure state.
- Which reservoir feeds which well and which pump is in which well comes from the flowsheet connections, not from "the first upstream unit" as in the legacy code.
- Pump failure prediction (legacy ESP-05) is out of scope: its model file does not exist.

## Done when

- The three use-cases work on the example data, and the numbers match the legacy app or the differences are explained.

## Report back

What was built, the comparison with legacy numbers, and anything gemini was missing.
