"""Seed curated demo incidents (demo-hardening skill: 5-8 covering the key cases).
Seeded rows carry source='seed' and are never presented as live data."""
from . import db as dbmod
from .context import get_context

SEEDS = [
    # issue, summary, urg, conf, review, verif, lat, lng, count, reasons
    ("pothole", "Pothole ~30cm on arterial road, two-wheelers swerving", 2, 0.82, 0, "standard",
     17.4415, 78.3800, 1, {"public_impact": ["arterial road"]}),
    ("pothole", "Deep pothole at school gate approach, children crossing", 4, 0.88, 0, "standard",
     17.4370, 78.4482, 3, {"public_impact": ["near school"], "context": ["recurring: 3 reports"],
                            "overrides": ["+1 for recurrence (3 reports)"]}),
    ("streetlight", "Streetlight pole dark for 3 nights on collector road", 2, 0.79, 0, "standard",
     17.4525, 78.5275, 1, {}),
    ("flooding", "Knee-deep water under Hitech City underpass, vehicles stuck", 5, 0.91, 0, "urgent",
     17.4435, 78.3772, 2, {"safety": ["life-risk hazard: major_flooding"],
                            "context": ["known flooding hotspot"],
                            "conditions": ["active rainfall worsens flooding (synthetic weather)"],
                            "overrides": ["minimum urgency 4: major_flooding"]}),
    ("sanitation", "Garbage overflow at market entrance, stray animals", 2, 0.84, 0, "standard",
     17.3616, 78.4747, 1, {}),
    ("other", "Something hanging from a pole, unclear from report", 1, 0.35, 1, "standard",
     17.4156, 78.4347, 1, {"overrides": ["low confidence -> review queue"]}),
    ("obstruction", "Construction debris dumped on carriageway, one lane blocked", 3, 0.77, 0, "standard",
     17.3690, 78.5250, 1, {"immediacy": ["obstruction is typically active/worsening"]}),
]


def run() -> None:
    conn = dbmod.connect()
    existing = conn.execute("SELECT COUNT(*) c FROM incidents WHERE source='seed'").fetchone()["c"]
    if existing:
        print("seed already present (%d incidents) — skipping" % existing)
        return
    for issue, summary, urg, conf, review, verif, lat, lng, count, reasons in SEEDS:
        ctx = get_context(lat, lng)
        sev = {"urgency": urg,
               "dimensions": {k: {"score": 0, "reasons": v} for k, v in reasons.items() if k != "overrides"},
               "overrides": reasons.get("overrides", []), "review_flag": bool(review),
               "verification": verif}
        evidence = {"observed": [summary], "claimed": [], "missing": ["seeded demo data"],
                    "hazards": []}
        iid = dbmod.insert_incident(
            conn, issue_type=issue,
            service_owner={"flooding": "Water/Sewerage", "obstruction": "HYDRAA"}.get(issue, "GHMC"),
            summary=summary, urgency=urg, confidence=conf, review_flag=bool(review),
            verification=verif, lat=lat, lng=lng, severity=sev, context=ctx,
            evidence=evidence, photo_path=None, source="seed")
        if count > 1:
            conn.execute("UPDATE incidents SET report_count=? WHERE id=?", (count, iid))
    conn.commit()
    print("seeded %d demo incidents (source='seed', synthetic)" % len(SEEDS))


if __name__ == "__main__":
    run()
