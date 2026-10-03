"""Duplicate detection: same issue + nearby coordinates + compatible time window
-> one incident with multiple reports."""
import sqlite3
from datetime import datetime, timedelta

from .context import haversine_m

MAX_DISTANCE_M = 120
MAX_AGE_H = 48


def find_matching_incident(db: sqlite3.Connection, issue_type: str, lat: float,
                           lng: float, now: datetime) -> int | None:
    cutoff = (now - timedelta(hours=MAX_AGE_H)).isoformat()
    rows = db.execute(
        "SELECT id, lat, lng FROM incidents WHERE issue_type=? AND status!='resolved' "
        "AND last_report_at>=?", (issue_type, cutoff)).fetchall()
    for row in rows:
        if haversine_m(lat, lng, row["lat"], row["lng"]) <= MAX_DISTANCE_M:
            return row["id"]
    return None
