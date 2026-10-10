import os
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("WILD_WITHIN_DB", os.path.join(APP_DIR, "wild_within.db"))
DEFAULT_TZ = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-public-deployment")

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def timezone():
    try:
        return ZoneInfo(DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")

def now_local():
    return datetime.now(timezone())

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Growth',
            description TEXT NOT NULL DEFAULT '',
            target_minutes INTEGER NOT NULL DEFAULT 15,
            reminder_time TEXT NOT NULL DEFAULT '',
            reminder_days TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            log_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'done',
            minutes INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            UNIQUE(habit_id, log_date)
        );
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            hypothesis TEXT NOT NULL DEFAULT '',
            duration_days INTEGER NOT NULL DEFAULT 30,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS experiment_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
            log_date TEXT NOT NULL,
            outcome TEXT NOT NULL DEFAULT '',
            rating INTEGER NOT NULL DEFAULT 3,
            note TEXT NOT NULL DEFAULT '',
            UNIQUE(experiment_id, log_date)
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM habits").fetchone()[0]
        if count == 0:
            today = now_local().date().isoformat()
            created = now_local().isoformat(timespec="seconds")
            samples = [
                ("Morning hydration", "Health", "Drink water after waking up.", 5, "07:00"),
                ("Move your body", "Fitness", "Walk, stretch or train.", 30, "18:00"),
                ("Read and reflect", "Mind", "Read a few pages and note one idea.", 20, "21:00"),
            ]
            db.executemany("""INSERT INTO habits
                (name,category,description,target_minutes,reminder_time,reminder_days,start_date,created_at)
                VALUES (?,?,?,?,?,'0,1,2,3,4,5,6',?,?)""",
                [(n,c,d,m,t,today,created) for n,c,d,m,t in samples])

init_db()

def get_day():
    value = request.args.get("date") or request.form.get("log_date") or now_local().date().isoformat()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return now_local().date()

def habit_is_scheduled(habit, day):
    start = date.fromisoformat(habit["start_date"])
    end = date.fromisoformat(habit["end_date"]) if habit["end_date"] else None
    return start <= day and (end is None or day <= end)

def dashboard_data(day):
    with connect() as db:
        habits = db.execute("SELECT * FROM habits WHERE active=1 ORDER BY id DESC").fetchall()
        logs = db.execute("SELECT * FROM logs WHERE log_date=?", (day.isoformat(),)).fetchall()
        log_map = {r["habit_id"]: r for r in logs}
        scheduled = [h for h in habits if habit_is_scheduled(h, day)]
        completed = sum(1 for h in scheduled if h["id"] in log_map and log_map[h["id"]]["status"] == "done")
        planned = len(scheduled)
        score = round(100 * completed / planned) if planned else 0
        week_start = day - timedelta(days=6)
        week_logs = db.execute("""
          SELECT log_date, COUNT(*) AS done_count FROM logs
          WHERE log_date BETWEEN ? AND ? AND status='done' GROUP BY log_date
        """, (week_start.isoformat(), day.isoformat())).fetchall()
        week_map = {r["log_date"]: r["done_count"] for r in week_logs}
        week = []
        for offset in range(6, -1, -1):
            d = day - timedelta(days=offset)
            week.append({"label": d.strftime("%a"), "date": d.isoformat(), "count": week_map.get(d.isoformat(), 0)})
        active_experiments = db.execute("SELECT * FROM experiments WHERE status='active' ORDER BY start_date DESC").fetchall()
        recent = db.execute("""SELECT logs.*, habits.name AS habit_name FROM logs
          JOIN habits ON habits.id=logs.habit_id ORDER BY updated_at DESC LIMIT 6""").fetchall()
    rows = []
    for h in scheduled:
        log = log_map.get(h["id"])
        rows.append({
            "habit": h,
            "status": log["status"] if log else "pending",
            "minutes": log["minutes"] if log else 0,
            "note": log["note"] if log else "",
        })
    return rows, completed, planned, score, week, active_experiments, recent

@app.route("/")
def index():
    day = get_day()
    rows, completed, planned, score, week, experiments, recent = dashboard_data(day)
    return render_template("index.html", selected_date=day.isoformat(), display_date=day.strftime("%A, %d %B %Y"),
        rows=rows, completed=completed, planned=planned, score=score, week=week,
        experiments=experiments, recent=recent, timezone_name=DEFAULT_TZ,
        today=now_local().date().isoformat())

@app.post("/habits/add")
def add_habit():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Give your activity a name first.", "error")
        return redirect(url_for("index"))
    try:
        minutes = max(1, min(1440, int(request.form.get("target_minutes", "15"))))
    except ValueError:
        minutes = 15
    reminder = request.form.get("reminder_time", "").strip()
    days = request.form.getlist("reminder_days")
    days_str = ",".join(str(int(d)) for d in days if d.isdigit() and 0 <= int(d) <= 6) or "0,1,2,3,4,5,6"
    start = request.form.get("start_date") or now_local().date().isoformat()
    end = request.form.get("end_date", "").strip()
    try:
        date.fromisoformat(start)
        if end:
            date.fromisoformat(end)
            if end < start:
                raise ValueError()
    except ValueError:
        flash("Please check the activity start/end dates.", "error")
        return redirect(url_for("index"))
    with connect() as db:
        db.execute("""INSERT INTO habits(name,category,description,target_minutes,reminder_time,reminder_days,start_date,end_date,created_at)
          VALUES(?,?,?,?,?,?,?,?,?)""",
          (name, request.form.get("category","Growth"), request.form.get("description","").strip(),
           minutes, reminder, days_str, start, end, now_local().isoformat(timespec="seconds")))
    flash("Activity added. You can log it each day.", "success")
    return redirect(url_for("index", date=start))

@app.post("/habits/<int:habit_id>/log")
def log_habit(habit_id):
    day = request.form.get("log_date") or now_local().date().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError:
        day = now_local().date().isoformat()
    status = request.form.get("status", "done")
    if status not in ("done", "missed", "skipped"):
        status = "done"
    try:
        minutes = max(0, min(1440, int(request.form.get("minutes", "0"))))
    except ValueError:
        minutes = 0
    note = request.form.get("note", "").strip()[:500]
    with connect() as db:
        exists = db.execute("SELECT id FROM habits WHERE id=?", (habit_id,)).fetchone()
        if not exists:
            flash("That activity no longer exists.", "error")
            return redirect(url_for("index", date=day))
        db.execute("""INSERT INTO logs(habit_id,log_date,status,minutes,note,updated_at)
          VALUES(?,?,?,?,?,?)
          ON CONFLICT(habit_id,log_date) DO UPDATE SET status=excluded.status, minutes=excluded.minutes,
          note=excluded.note, updated_at=excluded.updated_at""",
          (habit_id, day, status, minutes, note, now_local().isoformat(timespec="seconds")))
    flash("Daily record saved.", "success")
    return redirect(url_for("index", date=day))

@app.post("/habits/<int:habit_id>/edit")
def edit_habit(habit_id):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Activity name cannot be blank.", "error")
        return redirect(url_for("index"))
    try:
        minutes = max(1, min(1440, int(request.form.get("target_minutes", "15"))))
    except ValueError:
        minutes = 15
    with connect() as db:
        db.execute("""UPDATE habits SET name=?, category=?, description=?, target_minutes=?, reminder_time=?,
          reminder_days=?, start_date=?, end_date=? WHERE id=?""",
          (name, request.form.get("category","Growth"), request.form.get("description","").strip(),
           minutes, request.form.get("reminder_time",""), ",".join(request.form.getlist("reminder_days")) or "0,1,2,3,4,5,6",
           request.form.get("start_date") or now_local().date().isoformat(), request.form.get("end_date",""), habit_id))
    flash("Activity updated.", "success")
    return redirect(url_for("index"))

@app.post("/habits/<int:habit_id>/archive")
def archive_habit(habit_id):
    with connect() as db:
        db.execute("UPDATE habits SET active=0 WHERE id=?", (habit_id,))
    flash("Activity archived. Past records are preserved.", "success")
    return redirect(url_for("index"))

@app.route("/lab")
def lab():
    today = now_local().date()
    with connect() as db:
        experiments = db.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
        exp_rows = []
        for e in experiments:
            logs = db.execute("SELECT * FROM experiment_logs WHERE experiment_id=? ORDER BY log_date", (e["id"],)).fetchall()
            elapsed = max(0, min(e["duration_days"], (today - date.fromisoformat(e["start_date"])).days + 1))
            exp_rows.append({"experiment": e, "logs": logs, "elapsed": elapsed,
                             "progress": round(elapsed / e["duration_days"] * 100) if e["duration_days"] else 0})
    return render_template("lab.html", experiments=exp_rows, today=today.isoformat())

@app.post("/experiments/add")
def add_experiment():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Name your experiment first.", "error")
        return redirect(url_for("lab"))
    try:
        raw_duration = request.form.get("custom_duration", "").strip() or request.form.get("duration_days", "30")
        duration = max(1, min(365, int(raw_duration)))
    except ValueError:
        duration = 30
    try:
        start = date.fromisoformat(request.form.get("start_date") or now_local().date().isoformat())
    except ValueError:
        start = now_local().date()
    end = start + timedelta(days=duration - 1)
    with connect() as db:
        db.execute("""INSERT INTO experiments(title,hypothesis,duration_days,start_date,end_date,created_at)
          VALUES(?,?,?,?,?,?)""", (title, request.form.get("hypothesis","").strip(), duration,
          start.isoformat(), end.isoformat(), now_local().isoformat(timespec="seconds")))
    flash("Your commitment period has started.", "success")
    return redirect(url_for("lab"))

@app.post("/experiments/<int:exp_id>/log")
def log_experiment(exp_id):
    day = request.form.get("log_date") or now_local().date().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError:
        day = now_local().date().isoformat()
    try:
        rating = max(1, min(5, int(request.form.get("rating","3"))))
    except ValueError:
        rating = 3
    with connect() as db:
        exp = db.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
        if not exp:
            flash("Experiment not found.", "error")
            return redirect(url_for("lab"))
        # Only allow records inside the commitment dates, preserving an honest timeline.
        if day < exp["start_date"] or day > exp["end_date"]:
            flash("That date is outside this experiment's commitment period.", "error")
            return redirect(url_for("lab"))
        db.execute("""INSERT INTO experiment_logs(experiment_id,log_date,outcome,rating,note) VALUES(?,?,?,?,?)
          ON CONFLICT(experiment_id,log_date) DO UPDATE SET outcome=excluded.outcome,rating=excluded.rating,note=excluded.note""",
          (exp_id, day, request.form.get("outcome","completed"), rating, request.form.get("note","").strip()[:500]))
    flash("Experiment evidence saved.", "success")
    return redirect(url_for("lab"))

@app.post("/experiments/<int:exp_id>/finish")
def finish_experiment(exp_id):
    with connect() as db:
        db.execute("UPDATE experiments SET status='completed' WHERE id=?", (exp_id,))
    flash("Experiment marked complete. Its history remains available.", "success")
    return redirect(url_for("lab"))

@app.get("/api/reminders")
def reminders():
    day = now_local().date()
    weekday = str(day.weekday())
    with connect() as db:
        habits = db.execute("""SELECT id,name,reminder_time,reminder_days,start_date,end_date FROM habits
          WHERE active=1 AND reminder_time != ''""").fetchall()
        logs = db.execute("SELECT habit_id,status FROM logs WHERE log_date=?", (day.isoformat(),)).fetchall()
    log_map = {r["habit_id"]: r["status"] for r in logs}
    result = []
    for h in habits:
        if weekday not in h["reminder_days"].split(",") or day.isoformat() < h["start_date"] or (h["end_date"] and day.isoformat() > h["end_date"]):
            continue
        if log_map.get(h["id"]) == "done":
            continue
        result.append({"id": h["id"], "name": h["name"], "time": h["reminder_time"]})
    return jsonify({"date": day.isoformat(), "timezone": DEFAULT_TZ, "reminders": result})

@app.get("/health")
def health():
    return jsonify({"ok": True, "app": "WILD WITHIN"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
