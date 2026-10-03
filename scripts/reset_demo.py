"""Reset the demo to pristine seeded state: wipe ALL reports/incidents,
restart ID sequences, and re-insert the 7 curated seed incidents.
Usage: uv run python scripts/reset_demo.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import db as dbmod
from server import seed


def main() -> None:
    conn = dbmod.connect()
    conn.execute("DELETE FROM reports")
    conn.execute("DELETE FROM incidents")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('reports','incidents')")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    seed.run()  # inserts 7 seed incidents with IDs 1-7
    conn = dbmod.connect()
    counts = conn.execute(
        "SELECT source, COUNT(*) c FROM incidents GROUP BY source").fetchall()
    print("pristine state:", {r["source"]: r["c"] for r in counts})
    conn.close()


if __name__ == "__main__":
    main()
