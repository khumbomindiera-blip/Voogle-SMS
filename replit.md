# Voogle

An SMS-to-AI service that receives text messages via Africa's Talking, answers them using Google Gemini, and logs everything to an admin dashboard.

## Run & Operate

- `cd voogle && python app.py` — run the Flask app (port 5000)
- Workflow: **Voogle Flask App** — managed by Replit, auto-starts on project open

## Stack

- Python 3.11 + Flask 3
- Google Gemini (`google-genai` SDK, model: `gemini-2.0-flash`)
- SQLite (file: `voogle/voogle.db`)
- Africa's Talking SMS webhook

## Where things live

```
voogle/
  app.py          ← Flask routes (/, /sms, /admin, /health)
  database.py     ← SQLite init, insert, fetch helpers
  requirements.txt
  templates/
    dashboard.html  ← Admin dashboard UI
  voogle.db         ← SQLite database (created on first run, git-ignored)
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/sms` | Africa's Talking webhook — receives SMS, calls Gemini, returns plain text |
| GET | `/admin` | Admin dashboard (HTML) |
| GET | `/admin/api/queries` | All records as JSON |
| GET | `/health` | Health check |

## Secrets required

- `GEMINI_API_KEY` — Google AI Studio key (already set via Replit Secrets)

## Connecting Africa's Talking

See the **Pointers** section below.

## User preferences

_Populate as you build._

## Gotchas

- Africa's Talking sends POST form data; the `/sms` route reads `request.form.get("from")` and `request.form.get("text")`.
- AT expects a plain-text HTTP 200 response — Flask returns the Gemini reply directly.
- The SQLite database is created automatically on first startup.
- `google-generativeai` (old SDK) is deprecated — this project uses `google-genai` (new SDK).

## Pointers

- Africa's Talking dashboard: https://account.africastalking.com
- Google AI Studio (get API key): https://aistudio.google.com/app/apikey
- See the `pnpm-workspace` skill for the broader monorepo structure
