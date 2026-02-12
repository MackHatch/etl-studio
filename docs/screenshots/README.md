# Screenshots Guide

This directory should contain screenshots for the ETL Studio demo walkthrough.

## Browser & Size

- **Browser:** Chrome or Edge
- **Window size:** 1920×1080 (or full-screen)
- **Data:** Run `make demo` for seeded Demo Workspace (demo@etl.com)

## Checklist (per prompt)

- [ ] uploads.png — dataset page + upload area
- [ ] run-progress-sse.png — run detail with SSE progress
- [ ] results-table.png — results page with records table
- [ ] schema-rules.png — schema / rules editor
- [ ] compare-runs.png — compare Run A vs Run B

## Required Screenshots

### uploads.png
**Description:** Dataset page with upload CSV area  
**Capture:** After login as demo@etl.com, click "Demo: Marketing Spend", show upload section

### run-progress-sse.png
**Description:** Run detail page with live SSE progress bar and stats  
**Capture:** Navigate to `/runs/:id` for a run, show progress (or completed run)

### results-table.png
**Description:** Results page with imported records table and export buttons  
**Capture:** Navigate to `/runs/:id/results`, show table with records

### schema-rules.png
**Description:** Schema version and rules editor  
**Capture:** Navigate to `/datasets/:id/schema`, show rules (e.g. spend min)

### compare-runs.png
**Description:** Compare Run A vs Run B with KPI deltas  
**Capture:** Navigate to `/datasets/:id/compare` with leftRunId and rightRunId, show diff cards

## Capture Instructions

1. **Browser:** Use Chrome/Edge in full-screen or 1920x1080 window
2. **Data:** Use demo seed (`SEED_DEMO=true`) or create sample data
3. **Format:** PNG, 1920x1080 or similar, compressed
4. **Annotations:** Optional arrows/callouts for key features
5. **Naming:** Use numbered prefix (01-, 02-, etc.) for ordering

## Placeholder Images

Until screenshots are captured:

- `uploads.png` – Dataset + upload area
- `run-progress-sse.png` – Run progress with SSE
- `results-table.png` – Results table
- `schema-rules.png` – Schema rules editor
- `compare-runs.png` – Compare runs diff cards

## Usage in README

```markdown
![Uploads](docs/screenshots/uploads.png)
![Run progress](docs/screenshots/run-progress-sse.png)
![Results](docs/screenshots/results-table.png)
![Schema rules](docs/screenshots/schema-rules.png)
![Compare runs](docs/screenshots/compare-runs.png)
```
