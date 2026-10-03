"""Reset the demo to seeded-only state: delete live submissions, keep seed data.
Usage: uv run python scripts/reset_demo.py [--reseed]"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import db as dbmod


def main() -> None:
    conn = dbmod.connect()
    r = conn.execute("DELETE FROM reports WHERE source='live'").rowcount
    i = conn.execute("DELETE FROM incidents WHERE source='live'").rowcount
    conn.commit()
    conn.execute("VACUUM")
    seed_count = conn.execute("SELECT COUNT(*) c FROM incidents WHERE source='seed'").fetchone()["c"]
    print("live rows cleared (%d reports, %d incidents); %d seed incidents remain" % (r, i, seed_count))
    conn.close()
    if "--reseed" in sys.argv:
        from server import seed
        seed.run()


if __name__ == "__main__":
    main()
