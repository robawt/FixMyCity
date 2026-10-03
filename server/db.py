"""stdlib sqlite3 storage. Two tables: reports (raw citizen input + AI output)
and incidents (clustered tickets). source separates live vs seeded demo data."""
import json
import os
import sqlite3
from datetime import datetime

IS_VERCEL = os.environ.get("VERCEL") == "1"
DEFAULT_DB_PATH = ("/tmp/fixmycity.db" if IS_VERCEL
                   else os.path.join(os.path.dirname(__file__), "..", "data", "fixmycity.db"))
DB_PATH = os.environ.get("FMC_DB") or DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    text TEXT,
    photo_path TEXT,
    lat REAL, lng REAL, accuracy REAL,
    site_id TEXT,
    extraction_json TEXT,
    incident_id INTEGER,
    ai_provider TEXT,
    source TEXT NOT NULL DEFAULT 'live'
);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_type TEXT NOT NULL,
    service_owner TEXT NOT NULL,
    summary TEXT,
    urgency INTEGER NOT NULL,
    confidence REAL NOT NULL,
    review_flag INTEGER NOT NULL DEFAULT 0,
    verification TEXT NOT NULL DEFAULT 'standard',
    lat REAL, lng REAL,
    report_count INTEGER NOT NULL DEFAULT 1,
    first_report_at TEXT NOT NULL,
    last_report_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    severity_json TEXT,
    context_json TEXT,
    evidence_json TEXT,
    photo_path TEXT,
    source TEXT NOT NULL DEFAULT 'live'
);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def insert_incident(db: sqlite3.Connection, **kw) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = db.execute(
        "INSERT INTO incidents (issue_type, service_owner, summary, urgency, confidence,"
        " review_flag, verification, lat, lng, report_count, first_report_at, last_report_at,"
        " status, severity_json, context_json, evidence_json, photo_path, source)"
        " VALUES (?,?,?,?,?,?,?,?,?,1,?,?,'open',?,?,?,?,?)",
        (kw["issue_type"], kw["service_owner"], kw["summary"], kw["urgency"], kw["confidence"],
         int(kw["review_flag"]), kw["verification"], kw["lat"], kw["lng"], now, now,
         json.dumps(kw["severity"]), json.dumps(kw["context"]), json.dumps(kw["evidence"]),
         kw.get("photo_path"), kw.get("source", "live")))
    db.commit()
    return cur.lastrowid


def bump_incident(db: sqlite3.Connection, incident_id: int, urgency: int,
                  severity: dict, context: dict, now: datetime,
                  photo_path: str | None = None) -> int:
    # Preserve the first available photo so a grouped incident still shows
    # visual evidence in the admin dashboard.
    row = db.execute("SELECT photo_path FROM incidents WHERE id=?", (incident_id,)).fetchone()
    existing_photo = row["photo_path"] if row else None
    chosen_photo = existing_photo or photo_path
    db.execute(
        "UPDATE incidents SET report_count=report_count+1, last_report_at=?,"
        " urgency=?, severity_json=?, context_json=?, photo_path=? WHERE id=?",
        (now.isoformat(timespec="seconds"), urgency, json.dumps(severity),
         json.dumps(context), chosen_photo, incident_id))
    db.commit()
    return db.execute("SELECT report_count FROM incidents WHERE id=?",
                      (incident_id,)).fetchone()["report_count"]


def insert_report(db: sqlite3.Connection, **kw) -> int:
    cur = db.execute(
        "INSERT INTO reports (created_at, text, photo_path, lat, lng, accuracy, site_id,"
        " extraction_json, incident_id, ai_provider, source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (kw.get("created_at") or datetime.now().isoformat(timespec="seconds"),
         kw.get("text"), kw.get("photo_path"), kw.get("lat"), kw.get("lng"),
         kw.get("accuracy"), kw.get("site_id"), json.dumps(kw.get("extraction")),
         kw.get("incident_id"), kw.get("ai_provider"), kw.get("source", "live")))
    db.commit()
    return cur.lastrowid


def list_incidents(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM incidents ORDER BY urgency DESC, last_report_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("severity_json", "context_json", "evidence_json"):
            d[k[:-5]] = json.loads(d.pop(k) or "{}")
        d["review_flag"] = bool(d["review_flag"])
        out.append(d)
    return out


def set_status(db: sqlite3.Connection, incident_id: int, status: str) -> bool:
    cur = db.execute("UPDATE incidents SET status=? WHERE id=?", (status, incident_id))
    db.commit()
    return cur.rowcount > 0
