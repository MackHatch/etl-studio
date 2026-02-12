# Demo GIF Recording Guide

Instructions for recording a 10–15 second GIF of the ETL Studio 2-minute demo flow.

## Prerequisites

1. Run `make demo` (or have the app running with seeded data)
2. Screen recorder (e.g. [ScreenToGif](https://www.screentogif.com/), [LICEcap](https://www.cockos.com/licecap/), or built-in OS recording)
3. Browser at 1920×1080 or 1280×720

## Suggested 10–15s Flow

1. **Start:** Login page with cursor near email field  
2. **0–2s:** Enter `admin@acme.com` / `DemoPass123!` → Log in  
3. **2–4s:** Datasets list (shows Q1 Marketing Spend, Demo: Marketing Spend)  
4. **4–6s:** Click a dataset → Upload area or run list  
5. **6–8s:** Click a run → Run progress or results  
6. **8–10s:** Navigate to Analytics tab  
7. **10–12s:** Analytics dashboard with charts  
8. **End:** Fade or hold on dashboard  

## Alternative Shorter Flow (6–8s)

1. Login (pre-filled: admin@acme.com)  
2. Datasets list  
3. Click dataset → run results  
4. Analytics  

## Tips

- Pre-fill the login form before recording, or use a password manager for speed  
- Pause 0.5s on each key screen so viewers can read  
- Hide the cursor between actions if it distracts  
- Export as GIF (optimized, ~2–5MB) or MP4 (smaller, better quality)  

## Output

Save to `docs/demo.gif` (or `docs/demo.mp4`) for inclusion in README:

```markdown
## Demo

![2-minute demo](docs/demo.gif)
```
