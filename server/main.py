"""FixMyCity FastAPI backend — single process: API + static frontend + uploads."""
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import clustering, db as dbmod, kimi
from .context import get_context, SYNTHETIC_LABEL
from .schemas import IssueType, TicketOut
from .severity import route_owner, score_severity

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "..", "uploads")
STATIC = os.path.join(BASE, "..", "static")
os.makedirs(UPLOADS, exist_ok=True)

app = FastAPI(title="FixMyCity MVP")
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

MAX_PHOTO_BYTES = 6 * 1024 * 1024


@app.exception_handler(Exception)
async def clean_errors(request, exc):
    return JSONResponse(status_code=500, content={"detail": "internal error — report saved state unknown; please retry"})


@app.get("/api/health")
def health():
    return {"ok": True, "ai_provider": kimi.get_provider(),
            "model": os.environ.get("KIMI_MODEL", "kimi-k3") if kimi.get_provider() == "kimi" else None}


@app.get("/api/context-info")
def context_info():
    return {"synthetic": True, "label": SYNTHETIC_LABEL}


@app.post("/api/reports", response_model=TicketOut)
async def create_report(
    text: str | None = Form(None),
    photo: UploadFile | None = File(None),
    lat: float = Form(...), lng: float = Form(...),
    accuracy: float | None = Form(None),
    timestamp: str | None = Form(None),
    site_id: str | None = Form(None),
):
    if not (text and text.strip()) and not (photo and photo.filename):
        raise HTTPException(400, "Provide report text and/or a photo.")

    photo_bytes, photo_mime, photo_path = None, None, None
    if photo and photo.filename:
        photo_bytes = await photo.read()
        if len(photo_bytes) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Photo too large (max 6 MB).")
        photo_mime = photo.content_type or "image/jpeg"
        ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
        photo_path = str(uuid.uuid4())[:12] + ext
        with open(os.path.join(UPLOADS, photo_path), "wb") as f:
            f.write(photo_bytes)

    try:
        ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
    except ValueError:
        ts = datetime.now()

    extraction, provider = kimi.extract_report(text, photo_bytes, photo_mime,
                                               {"timestamp": ts.isoformat(), "site_id": site_id})
    ctx = get_context(lat, lng, ts)
    now = datetime.now()
    conn = dbmod.connect()
    match = clustering.find_matching_incident(conn, extraction.issue_type.value, lat, lng, now)
    age_h = 0.0
    if match:
        first = conn.execute("SELECT first_report_at, report_count FROM incidents WHERE id=?",
                             (match,)).fetchone()
        age_h = (now - datetime.fromisoformat(first["first_report_at"])).total_seconds() / 3600
        count_for_scoring = first["report_count"] + 1
    else:
        count_for_scoring = 1

    sev = score_severity(extraction, ctx, count_for_scoring, age_h)
    owner = route_owner(extraction.issue_type, ctx["jurisdiction"])
    evidence = {"observed": extraction.observed, "claimed": extraction.claimed,
                "missing": extraction.missing, "hazards": extraction.hazards}

    if match:
        count = dbmod.bump_incident(conn, match, sev.urgency, sev.model_dump(), ctx, now)
        incident_id, duplicate_of = match, match
    else:
        incident_id = dbmod.insert_incident(
            conn, issue_type=extraction.issue_type.value, service_owner=owner.value,
            summary=extraction.summary, urgency=sev.urgency, confidence=extraction.confidence,
            review_flag=sev.review_flag, verification=sev.verification, lat=lat, lng=lng,
            severity=sev.model_dump(), context=ctx, evidence=evidence, photo_path=photo_path)
        count, duplicate_of = 1, None

    dbmod.insert_report(conn, text=text, photo_path=photo_path, lat=lat, lng=lng,
                        accuracy=accuracy, site_id=site_id,
                        extraction=extraction.model_dump(mode="json"),
                        incident_id=incident_id, ai_provider=provider)
    conn.close()

    return TicketOut(
        incident_id=incident_id, issue_type=extraction.issue_type, service_owner=owner,
        urgency=sev.urgency, confidence=round(extraction.confidence, 2),
        review_flag=sev.review_flag, verification=sev.verification,
        summary=extraction.summary, observed=extraction.observed,
        claimed=extraction.claimed, missing=extraction.missing,
        severity_reasons={k: v.reasons for k, v in sev.dimensions.items() if v.reasons} |
                          ({"overrides": sev.overrides} if sev.overrides else {}),
        duplicate_of=duplicate_of, report_count=count,
        context_label=SYNTHETIC_LABEL, data_source="live", ai_provider=provider)


@app.get("/api/incidents")
def incidents():
    conn = dbmod.connect()
    out = dbmod.list_incidents(conn)
    conn.close()
    return {"incidents": out, "context_label": SYNTHETIC_LABEL}


class StatusIn(BaseModel):
    status: str


@app.patch("/api/incidents/{incident_id}/status")
def update_status(incident_id: int, body: StatusIn):
    if body.status not in ("open", "in_progress", "resolved"):
        raise HTTPException(400, "status must be open|in_progress|resolved")
    conn = dbmod.connect()
    ok = dbmod.set_status(conn, incident_id, body.status)
    conn.close()
    if not ok:
        raise HTTPException(404, "incident not found")
    return {"ok": True}


@app.get("/")
def citizen_page():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/admin")
def admin_page():
    return FileResponse(os.path.join(STATIC, "admin.html"))
