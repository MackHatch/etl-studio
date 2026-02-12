# Screenshots Guide

This directory should contain screenshots for the ETL Studio demo walkthrough. Use these placeholders and capture instructions.

## Browser & Size

- **Browser:** Chrome or Edge
- **Window size:** 1920×1080 (or full-screen)
- **Data:** Run `make demo` for seeded Acme Marketing org and datasets

## Checklist

- [ ] 01-login.png
- [ ] 02-dashboard.png (datasets list - first page after login)
- [ ] 03-dataset-upload.png
- [ ] 04-mapping.png
- [ ] 05-run-progress.png
- [ ] 06-results.png
- [ ] 07-analytics.png
- [ ] 08-admin-runs.png
- [ ] 09-compare-runs.png
- [ ] 10-jaeger.png
- [ ] 11-minio-console.png (S3 storage)

## Required Screenshots

### 1. Login Page
**File:** `01-login.png`  
**Description:** Login form with email/password fields  
**Capture:** Navigate to `/login`, show the form

### 2. Dashboard (Datasets List)
**File:** `02-dashboard.png`  
**Description:** Datasets list - first page after login, shows Acme Marketing datasets  
**Capture:** After login as admin@acme.com, show `/datasets` page

### 3. Dataset Detail with Upload
**File:** `03-dataset-upload.png`  
**Description:** Dataset detail page showing upload form  
**Capture:** Click a dataset, show upload CSV section

### 4. Mapping Configuration
**File:** `04-mapping.png`  
**Description:** Column mapping page with dropdowns for canonical fields  
**Capture:** After upload, show `/runs/:id/mapping` with column selects

### 5. Run Progress (SSE)
**File:** `05-run-progress.png`  
**Description:** Run detail page showing live progress bar and stats  
**Capture:** After starting run, show `/runs/:id` with progress updating

### 6. Results Table
**File:** `06-results.png`  
**Description:** Results page showing imported records table  
**Capture:** Navigate to `/runs/:id/results`, show table with records

### 7. Analytics Dashboard
**File:** `07-analytics.png`  
**Description:** Analytics page with charts (by day, by channel) and KPIs  
**Capture:** Navigate to `/analytics`, select dataset, show charts

### 8. Admin Runs Dashboard
**File:** `08-admin-runs.png`  
**Description:** Admin runs list with filters and live updates  
**Capture:** As admin user, navigate to `/admin/runs`, show table

### 9. Run Attempts History
**File:** `09-attempts.png`  
**Description:** Run detail showing attempt history with retries  
**Capture:** Show a failed/retried run with attempts panel

### 10. Jaeger Tracing (if enabled)
**File:** `10-jaeger.png`  
**Description:** Jaeger UI showing trace spans for upload → worker → SSE  
**Capture:** With tracing enabled, show Jaeger UI with trace timeline

### 11. MinIO Console (S3 storage)
**File:** `11-minio-console.png`  
**Description:** MinIO console showing etl-uploads bucket  
**Capture:** http://localhost:9001, login with MINIO_ROOT_USER/MINIO_ROOT_PASSWORD

## Capture Instructions

1. **Browser:** Use Chrome/Edge in full-screen or 1920x1080 window
2. **Data:** Use demo seed (`SEED_DEMO=true`) or create sample data
3. **Format:** PNG, 1920x1080 or similar, compressed
4. **Annotations:** Optional arrows/callouts for key features
5. **Naming:** Use numbered prefix (01-, 02-, etc.) for ordering

## Placeholder Images

Until screenshots are captured, use placeholder images:

- `01-login.png` – [Placeholder: Login form]
- `02-dashboard.png` – [Placeholder: Datasets/dashboard list]
- `03-dataset-upload.png` – [Placeholder: Upload form]
- `04-mapping.png` – [Placeholder: Mapping page]
- `05-run-progress.png` – [Placeholder: Progress view]
- `06-results.png` – [Placeholder: Results table]
- `07-analytics.png` – [Placeholder: Analytics dashboard]
- `08-admin-runs.png` – [Placeholder: Admin dashboard]
- `09-compare-runs.png` – [Placeholder: Compare runs page]
- `10-jaeger.png` – [Placeholder: Jaeger trace view]
- `11-minio-console.png` – [Placeholder: MinIO bucket view]

## Usage in README

Add screenshots to the main README.md:

```markdown
## Screenshots

![Login](docs/screenshots/01-login.png)
![Datasets](docs/screenshots/02-datasets-list.png)
...
```
