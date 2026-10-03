"""FixMyCity FastAPI backend — single process: API + static frontend + uploads."""
import os
import socket
import struct
import uuid
import zlib
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import qrcode

from . import clustering, db as dbmod, kimi
from .context import get_context, SYNTHETIC_LABEL
from .schemas import IssueType, TicketOut
from .severity import route_owner, score_severity

BASE = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = os.environ.get("VERCEL") == "1"
UPLOADS = os.path.join("/tmp", "fixmycity-uploads") if IS_VERCEL else os.path.join(BASE, "..", "uploads")
STATIC = os.path.join(BASE, "..", "static")
os.makedirs(UPLOADS, exist_ok=True)

app = FastAPI(title="FixMyCity MVP")
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _ensure_vercel_seed() -> None:
    """Seed the demo database in Vercel's ephemeral /tmp storage on cold start."""
    if not IS_VERCEL:
        return
    conn = dbmod.connect()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM incidents WHERE source='seed'").fetchone()["c"]
    finally:
        conn.close()
    if count == 0:
        from .seed import run as seed_run
        seed_run()


_ensure_vercel_seed()

MAX_PHOTO_BYTES = int(os.environ.get("FMC_MAX_PHOTO_BYTES", "3500000"))


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
    qr_lat: float | None = Form(None), qr_lng: float | None = Form(None),
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
    # Prefer live GPS for the incident location. Keep QR coordinates as secondary
    # provenance/context so a location-generated QR remains useful on weak GPS.
    ctx = get_context(lat, lng, ts)
    if qr_lat is not None and qr_lng is not None:
        ctx["qr_location"] = {"lat": qr_lat, "lng": qr_lng}
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
        count = dbmod.bump_incident(conn, match, sev.urgency, sev.model_dump(), ctx, now, photo_path)
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


def _is_loopback_host(host: str) -> bool:
    host = (host or "").split(":", 1)[0].strip("[]").lower()
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _best_local_ip() -> str | None:
    """Return the machine LAN IPv4 without sending application traffic."""
    candidates = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # UDP connect only selects a local interface; it does not send data.
            sock.connect(("192.0.2.1", 9))
            candidates.append(sock.getsockname()[0])
        finally:
            sock.close()
    except OSError:
        pass
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.append(item[4][0])
    except OSError:
        pass
    for ip in candidates:
        if ip and not ip.startswith("127."):
            return ip
    return None


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + chunk_type + data +
            struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF))


def _qr_png(payload: str, scale: int = 6, border: int = 4) -> bytes:
    """Create a tiny, dependency-free PNG from qrcode's boolean matrix."""
    qr = qrcode.QRCode(version=None, box_size=1, border=border,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    height = len(matrix) * scale
    width = len(matrix[0]) * scale

    raw = bytearray()
    for row in matrix:
        pixels = bytearray()
        for dark in row:
            pixels.extend((0 if dark else 255,) * scale)
        for _ in range(scale):
            raw.append(0)  # filter type: None
            raw.extend(pixels)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" +
            _png_chunk(b"IHDR", ihdr) +
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            _png_chunk(b"IEND", b""))


def _qr_origin(request: Request) -> str:
    """Build an origin a second device can actually reach."""
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    scheme = (forwarded_proto or request.url.scheme).split(",", 1)[0].strip()
    host = (forwarded_host or request.headers.get("host") or request.url.netloc).split(",", 1)[0].strip()

    if _is_loopback_host(host):
        lan_ip = _best_local_ip()
        if lan_ip:
            raw_port = request.url.port
            if raw_port:
                host = f"{lan_ip}:{raw_port}"
            else:
                host = lan_ip
    return f"{scheme}://{host}"


@app.get("/api/qr")
def generate_location_qr(
    request: Request,
    lat: float,
    lng: float,
    accuracy: float | None = None,
):
    """Generate a lightweight SVG QR that opens a location-anchored report page."""
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(400, "Invalid coordinates")
    if accuracy is not None and (accuracy < 0 or accuracy > 100000):
        raise HTTPException(400, "Invalid location accuracy")

    from urllib.parse import urlencode

    params = {"lat": f"{lat:.6f}", "lng": f"{lng:.6f}"}
    if accuracy is not None:
        params["qr_accuracy"] = f"{accuracy:.0f}"

    # The QR should be useful when printed/scanned on a second device.
    # If the page is being served from localhost during development, replace
    # loopback with the machine's LAN IP rather than generating an unusable QR.
    url = f"{_qr_origin(request)}/?{urlencode(params)}"

    png = _qr_png(url)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-FixMyCity-QR-URL": url,
        },
    )


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
