"""AI extraction providers. Kimi (OpenAI-compatible, vision) with a mock fallback.
Interface: extract_report(text, photo_bytes, photo_mime, meta) -> ExtractionResult
AI extracts evidence only — severity is computed by policy code elsewhere."""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

from .schemas import ExtractionResult, IssueType

API_URL = "https://api.moonshot.ai/v1/chat/completions"

PROMPT = """Extract civic-issue evidence from a citizen report (text +/- photo). Reply ONLY with JSON:
{"issue_type":"pothole|road_damage|streetlight|water_leak|drainage|flooding|sanitation|fallen_tree|electrical_hazard|obstruction|other",
"observed":["facts directly stated or visible"],"claimed":["unverified citizen claims"],"missing":["important unknowns"],
"hazards":["exposed_wiring","electric_shock_risk","standing_water","major_flooding","traffic_obstruction","structural_collapse","sharp_debris","contamination","fall_risk","fire_risk","drowning_risk"],
"confidence":0.0,"summary":"one factual line"}
Rules: never invent locations, dates, measurements, causes, or counts. Emotional wording is not evidence. Use empty lists when unknown. Photo: describe only visible evidence. hazards: include only those that apply, else []."""


class KimiError(Exception):
    pass


def _parse_json(content: str) -> dict:
    content = content.strip()
    content = re.sub(r"^```(json)?|```$", "", content, flags=re.M).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _to_result(data: dict, photo_used: bool) -> ExtractionResult:
    try:
        data["issue_type"] = IssueType(data.get("issue_type", "other"))
    except ValueError:
        data["issue_type"] = IssueType.other
    allowed = {k for k in ("issue_type", "observed", "claimed", "missing", "hazards", "confidence", "summary")}
    data = {k: v for k, v in data.items() if k in allowed}
    r = ExtractionResult(**data)
    r.confidence = max(0.0, min(1.0, float(r.confidence)))
    return r


def kimi_extract(text: str | None, photo_bytes: bytes | None, photo_mime: str | None,
                 meta: dict, model: str, api_key: str) -> ExtractionResult:
    user_text = "Citizen report text: %s\nReport metadata: %s" % (
        (text or "(none provided)").strip()[:2000],
        json.dumps({k: meta[k] for k in ("timestamp", "site_id") if meta.get(k)}),
    )
    content: list[dict] = []
    if photo_bytes:
        b64 = base64.b64encode(photo_bytes).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": "data:%s;base64,%s" % (photo_mime or "image/jpeg", b64)}})
    content.append({"type": "text", "text": PROMPT + "\n\n" + user_text})
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"}, "max_tokens": 1600}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + api_key,
                                          "Content-Type": "application/json"})
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=75) as resp:
                r = json.load(resp)
            msg = r["choices"][0]["message"].get("content") or ""
            if not msg.strip():
                raise KimiError("empty model response")
            return _to_result(_parse_json(msg), photo_used=bool(photo_bytes))
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            last_err = KimiError("Kimi HTTP %s: %s" % (e.code, detail))
            if e.code < 500:
                break  # 4xx won't fix itself on retry
        except (urllib.error.URLError, TimeoutError, KimiError, json.JSONDecodeError, KeyError) as e:
            last_err = e if isinstance(e, KimiError) else KimiError(str(e))
        if attempt == 1:
            time.sleep(2)
    raise last_err or KimiError("unknown Kimi failure")


MOCK_KEYWORDS = {
    IssueType.pothole: ["pothole"],
    IssueType.road_damage: ["road damage", "cracked road", "road caved"],
    IssueType.streetlight: ["streetlight", "street light", "lamp", "no light"],
    IssueType.water_leak: ["water leak", "pipe burst", "leaking pipe", "leak", "leaking"],
    IssueType.drainage: ["drain", "drainage", "blocked drain", "sewage overflow"],
    IssueType.flooding: ["flood", "waterlogging", "water logging", "submerged"],
    IssueType.sanitation: ["garbage", "trash", "sanitation", "waste"],
    IssueType.fallen_tree: ["fallen tree", "tree fell", "tree down"],
    IssueType.electrical_hazard: ["wire", "electric", "sparking", "transformer"],
    IssueType.obstruction: ["obstruction", "blocked road", "debris", "encroach"],
}
MOCK_HAZARDS = {
    "wire": ["exposed_wiring", "electric_shock_risk"], "sparking": ["exposed_wiring", "fire_risk"],
    "flood": ["standing_water", "major_flooding"], "waterlogging": ["standing_water"],
    "submerged": ["standing_water", "drowning_risk"], "blocked road": ["traffic_obstruction"],
    "debris": ["sharp_debris"], "tree": ["traffic_obstruction"],
}


def mock_extract(text: str | None, photo_bytes: bytes | None, photo_mime: str | None,
                 meta: dict) -> ExtractionResult:
    """Deterministic keyword fallback so the demo runs without an API key.
    Clearly limited: low confidence, flags photo as unanalyzed."""
    t = (text or "").lower()
    issue = IssueType.other
    for it, kws in MOCK_KEYWORDS.items():
        if any(k in t for k in kws):
            issue = it
            break
    hazards: list[str] = []
    for kw, hz in MOCK_HAZARDS.items():
        if kw in t:
            hazards.extend(h for h in hz if h not in hazards)
    observed = [text.strip()[:200]] if text and text.strip() else []
    missing = [] if photo_bytes else ["no photo provided"]
    if photo_bytes:
        missing.append("photo not analyzed (mock provider)")
    return ExtractionResult(issue_type=issue, observed=observed, claimed=[],
                            missing=missing, hazards=hazards,
                            confidence=0.45 if issue != IssueType.other else 0.3,
                            summary=(text or "Report submitted").strip()[:140])


def get_provider() -> str:
    mode = os.environ.get("FMC_AI_PROVIDER", "auto").lower()
    if mode == "mock":
        return "mock"
    if mode == "kimi":
        return "kimi"
    return "kimi" if os.environ.get("KIMI_API_KEY") else "mock"


def extract_report(text: str | None, photo_bytes: bytes | None, photo_mime: str | None,
                   meta: dict) -> tuple[ExtractionResult, str]:
    provider = get_provider()
    if provider == "kimi":
        key = os.environ.get("KIMI_API_KEY", "")
        model = os.environ.get("KIMI_MODEL", "kimi-k3")
        try:
            return kimi_extract(text, photo_bytes, photo_mime, meta, model, key), "kimi"
        except KimiError:
            if os.environ.get("FMC_AI_PROVIDER", "auto").lower() == "kimi":
                raise
            # auto mode: degrade gracefully so the demo never dies
            return mock_extract(text, photo_bytes, photo_mime, meta), "mock"
    return mock_extract(text, photo_bytes, photo_mime, meta), "mock"
