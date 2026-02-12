# Demo GIF Recording Guide

Record a 10–15 second GIF of the ETL Studio flow: **upload → start → progress → results**.

## Prerequisites

1. Run `make demo` (or have app running with seeded data)
2. Screen recorder (e.g. [ScreenToGif](https://www.screentogif.com/), [LICEcap](https://www.cockos.com/licecap/))
3. Browser at 1920×1080 or 1280×720

## Suggested Flow (upload → start → progress → results)

1. **Login** — `demo@etl.com` / `DemoPass123!`
2. **Upload** — Go to dataset "Demo: Marketing Spend" → upload sample.csv (or use Download from /demo)
3. **Mapping** — Map columns (date, campaign, channel, spend) → Save → Start import
4. **Progress (SSE)** — Watch run page with live progress bar updating
5. **Results** — Navigate to View results → show table with records

## Shorter Alternative (6–8s)

1. Login (pre-filled)
2. Click dataset → show upload
3. Click Run A or B → show run/results
4. Compare page → show diff cards

## Tips

- Pause 0.5s on each key screen
- Export as GIF (~2–5MB) or MP4 (smaller, better quality)
- Hide cursor between actions if it distracts

## Output

Save to `docs/demo.gif` (or `docs/demo.mp4`):

```markdown
## Demo

![2-minute demo](docs/demo.gif)
```
