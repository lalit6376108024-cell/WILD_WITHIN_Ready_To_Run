# WILD WITHIN — Ready-to-run Habit & Growth App

A Flask + SQLite starter application with a responsive nature-inspired dashboard, customizable activities, daily performance, date review, browser reminders while the dashboard is open, and time-bound Habit Lab experiments.

## Run on Windows

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/ (select **Add Python to PATH** during setup).
2. Extract this ZIP to a normal folder, for example `D:\WILD_WITHIN_Ready_To_Run`.
3. Open PowerShell in that folder.
4. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

5. Open http://127.0.0.1:5000 in your browser.

If `py` is not recognized, try `python -m venv .venv` and use `python -m pip install -r requirements.txt`. Use `python -m pip`, not `pip` by itself, when PowerShell cannot find pip.

## Features

- Create, edit, and archive personal activities; past logs are preserved.
- Set a category, description, planned minutes, date range, reminder time, and reminder weekdays.
- Review another date and log done / missed / intentionally skipped, actual minutes, and a note.
- Daily performance is completed scheduled activities divided by scheduled activities for the selected day.
- Seven-day completion chart.
- Habit Lab experiments with 7, 14, 30, 90 or custom duration (1–365 days), start/end dates, daily outcome, 1–5 self-rating, and reflection history.
- Experiment entries are restricted to the committed date range; missed days are not hidden.
- Browser notifications, if allowed, while the dashboard tab is open.
- SQLite data persists in `wild_within.db` on the machine/container where it runs.

## Important reminder limitation

This starter checks reminders from the open browser tab and can display browser notifications if permission is granted. It does **not** guarantee notifications when the browser is closed or the device is asleep. For that, implement Web Push + a server-side scheduler (and on Android, native notification scheduling). Do not use this starter as a critical alarm system.

## Deploy on Render

1. Push this project to a GitHub repository.
2. In Render, create a new Web Service from that repository.
3. Render can use `render.yaml`; otherwise set build command `pip install -r requirements.txt` and start command `gunicorn app:app`.
4. Set `APP_TIMEZONE=Asia/Kolkata` and a long random `SECRET_KEY`.
5. **Persistence warning:** Render's local filesystem may be ephemeral on a standard service. For durable user data, attach a persistent disk and set `WILD_WITHIN_DB` to a database path on that disk, or migrate to managed PostgreSQL before inviting real users.

## Current scope

This is a runnable single-user prototype, not a finished multi-user production service. It has no login, account isolation, cloud backup, or true background push scheduler. Add those before storing private data or opening the app to the public.
