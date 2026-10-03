# FixMyCity Demo-Readiness Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Take the already-built and verified MVP to a judge-proof demo on the golden path: QR/web -> text/photo -> GPS -> multimodal AI (Kimi K3) -> evidence-based severity -> service owner -> structured ticket -> admin dashboard.

**Architecture:** Single FastAPI process serving API + static frontend + uploads; stdlib sqlite3 storage; Kimi K3 (vision, JSON mode) for evidence extraction with a deterministic mock fallback; policy code (not AI) computes severity; synthetic Hyderabad context for traffic/weather/hotspots, always labeled SYNTHETIC.

**Tech Stack:** Python 3.11, uv, FastAPI, uvicorn, pydantic, vanilla JS (no build step), Kimi Open Platform (api.moonshot.ai/v1).

---

## Current state (verified 2026-10-03, do NOT rebuild)

Working and smoke-tested (15/15 ad-hoc checks + 13/13 golden-path checks + 1 live Kimi text+photo call):

- `server/schemas.py` — contract enums + pydantic models (single source of truth from `docs/product-contract.md`)
- `server/kimi.py` — Kimi client (vision + json_object, max_tokens 1600, no temperature param, 1 retry) + mock provider; `FMC_AI_PROVIDER=auto|kimi|mock`
- `server/severity.py` — 5-dimension evidence-only scoring, min-4 hazard overrides, high-risk+low-confidence -> urgent review; owner routing
- `server/context.py` — 10 synthetic Hyderabad zones, traffic by hour, static weather, SYNTHETIC label
- `server/clustering.py` — duplicate grouping: same issue <=120m, <=48h
- `server/db.py` — sqlite3, reports+incidents, `source` (live/seed), `FMC_DB` env override
- `server/main.py` — POST /api/reports, GET /api/incidents, PATCH status, /api/health, static hosting
- `static/index.html`, `static/admin.html`, `static/style.css` — citizen page (GPS, photo preview, `?site=` QR param) + admin dashboard (auto-refresh 15s)
- `server/seed.py` — 7 synthetic demo incidents (already seeded)
- `scripts/smoke.py`, `scripts/live_kimi_test.py` — verification scripts
- Server currently running: `proc_e02cb2d4b775`, http://127.0.0.1:8000, provider=kimi

## Gaps to close (this plan)

1. Not version-controlled (no git repo) — one bad edit can kill the demo.
2. Server binds 127.0.0.1 — a judge's phone cannot reach it.
3. No QR code — the QR entry of the golden path is unexercised.
4. No one-command demo reset (clear live rows, keep seed).
5. Real phone photo never tested (size, EXIF orientation, mobile browser flow).
6. Failure paths not rehearsed (AI down, GPS denied, empty submission).

---

### Task 1: Git safety net

**Objective:** Version-control the working MVP before any further edits.

**Files:** Create: `.git/` (via init). No code changes.

**Step 1:** Run:
```bash
cd /c/Users/ayman/projects/nextgenhackproject/app
git init && git add -A && git commit -m "feat: working MVP (verified golden path)"
```
Expected: commit succeeds; `.env`, `.venv/`, `data/`, `uploads/` excluded by existing `.gitignore`. Verify with `git status --short` (empty) and `git show --stat HEAD | grep -c "\.env"` -> `0`.

### Task 2: Demo reset script

**Objective:** One command restores the demo to seeded-only state between rehearsal runs.

**Files:** Create: `scripts/reset_demo.py`

**Step 1: Write script** — connect via `server/db.py`, `DELETE FROM reports WHERE source='live'`, `DELETE FROM incidents WHERE source='live'`, `VACUUM`, print remaining seed count. Accept `--reseed` to also run `server.seed.run()`.

**Step 2: Verify** — Run:
```bash
uv run python scripts/reset_demo.py
```
Expected output: `live rows cleared; 7 seed incidents remain`. Then `curl -s http://127.0.0.1:8000/api/incidents` shows only `source='seed'` rows (restart not needed; DB is per-request).

**Step 3: Commit** — `git add scripts/reset_demo.py && git commit -m "chore: demo reset script"`

### Task 3: LAN serving for phones

**Objective:** Judge's phone on the same Wi-Fi can open the app.

**Files:** Modify: `README.md` (run instructions). No server code change.

**Step 1:** Kill the current background server (`proc_e02cb2d4b775`) and restart with LAN binding:
```bash
cd /c/Users/ayman/projects/nextgenhackproject/app
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```
(background process, keep running for the demo)

**Step 2:** Get LAN IP: `ipconfig | grep -A4 "Wireless LAN adapter Wi-Fi" | grep "IPv4"` -> note e.g. `192.168.x.x`.

**Step 3: Verify reachability** — from this machine: `curl -s http://<LAN-IP>:8000/api/health` -> `{"ok":true,...}`. If Windows Firewall prompts for python/uvicorn, allow Private networks. If the venue Wi-Fi has client isolation (phone cannot reach laptop), fallback: phone hotspot from the laptop's own hotspot, or demo on the laptop browser itself.

**Step 4: Commit** — README update: `git commit -am "docs: LAN serving instructions"`

### Task 4: QR code for the golden path

**Objective:** Physical QR opens `http://<LAN-IP>:8000/?site=HACKATHON-BOOTH-1` on a judge's phone.

**Files:** Create: `scripts/make_qr.py`. Modify: `pyproject.toml` (dev dep).

**Step 1:** `uv add --dev qrcode` (pure-python, no system deps; PNG via qrcode's SVG/terminal factory to avoid Pillow: use `qrcode`'s built-in ASCII print or SVG image factory).

**Step 2: Write script** — takes `BASE_URL` and `SITE_ID` args, builds the URL, prints an ASCII QR to the terminal AND writes `docs/demo-qr.svg`:
```python
import sys, qrcode
from qrcode.image.svg import SvgImage
url = sys.argv[1]  # e.g. http://192.168.1.20:8000/?site=HACKATHON-BOOTH-1
img = qrcode.make(url, image_factory=SvgImage)
img.save("docs/demo-qr.svg")
qrcode.QRCode(border=1).print_ascii()  # terminal preview optional
print("QR ->", url)
```

**Step 3: Verify** — Run with the Task-3 LAN URL; open `docs/demo-qr.svg` in a browser; scan with a phone camera; expected: citizen page loads with location prompt. Submit one real report from the phone.

**Step 4: Commit** — `git add -A && git commit -m "feat: QR entry point generator"`

### Task 5: Real-phone golden-path test

**Objective:** Prove the full golden path on actual hardware, not curl.

**Files:** None (test-only task). May create fixes if a real bug appears.

**Step 1:** On the phone: scan QR -> allow location -> type "Huge water logging near the bus stop, cars stuck" -> take a real photo -> submit.

**Step 2:** Expected on phone within ~30s: ticket card with `issue_type=flooding` or `drainage`, urgency badge, owner `Water/Sewerage`, observed-vs-claimed evidence lists, `ai_provider: kimi`, SYNTHETIC context label. If processing exceeds 45s, note it — spinner text already warns ~15s; update copy to "~30s" in `static/index.html` if reality demands.

**Step 3:** On the laptop: open `http://<LAN-IP>:8000/admin` -> the phone's report appears at/near the top with `live` badge; set it `in progress` -> status persists after refresh.

**Step 4:** Check uploaded photo renders: click `photo` link on the incident card. If EXIF orientation is wrong, accept it for the demo (do NOT add Pillow in the 2-hour window unless a judge-visible blocker).

**Step 5: Commit** any fixes: `git commit -am "fix: mobile golden path"`

### Task 6: Failure-path rehearsal

**Objective:** Every failure shows a graceful state, never a stack trace or infinite spinner.

**Files:** None unless a bug is found.

**Step 1: AI down** — restart server with `FMC_AI_PROVIDER=mock`, submit a report; expected: ticket still returned (keyword classification, `ai_provider: mock`, lower confidence, honest "photo not analyzed" in missing info). Restart back to `auto` (kimi) after.

**Step 2: GPS denied** — in browser devtools or a phone with location off: click submit; expected: inline error "Location required — click Use my location", no spinner hang.

**Step 3: Empty submission** — clear text, no photo; expected: `400 Provide report text and/or a photo.` shown inline (already covered by ad-hoc check; confirm UI displays `detail` cleanly).

**Step 4: Dashboard empty state** — run `scripts/reset_demo.py` against a scratch `FMC_DB`, load /admin; expected: seed incidents still render (never empty). 

### Task 7: Final verification pass (stop condition)

**Objective:** Re-prove everything after all changes, from a clean DB.

**Step 1:**
```bash
uv run python scripts/reset_demo.py --reseed
uv run python scripts/smoke.py 8000
uv run python scripts/live_kimi_test.py 8000
```
Expected: smoke -> `ALL CHECKS PASSED`; live test -> real Kimi ticket JSON with `ai_provider: kimi`, observed/claimed separation.

**Step 2:** Phone: one more QR report; admin shows it. 

**Step 3:** `git add -A && git commit -m "chore: demo ready (verified)"` — then STOP. No further "improvements".

---

## Files likely to change

- Create: `scripts/reset_demo.py`, `scripts/make_qr.py`, `docs/demo-qr.svg`
- Modify: `README.md` (LAN/QR/reset instructions), `pyproject.toml` + `uv.lock` (dev dep `qrcode`), possibly copy tweak in `static/index.html`
- No changes expected in `server/` — it is verified; touch it only if Task 5/6 exposes a real bug.

## Tests / validation

- `scripts/smoke.py 8000` — 13 golden-path checks, must print ALL CHECKS PASSED
- `scripts/live_kimi_test.py 8000` — one real Kimi text+photo call, must return a coherent ticket
- Phone scan -> submit -> admin render (manual, golden path)
- Failure paths per Task 6

## Risks, tradeoffs, open questions

- **Venue Wi-Fi client isolation** — phone may not reach laptop. Mitigation: laptop hotspot, or demo entirely on laptop browser (acceptable fallback; QR is still showable).
- **Kimi latency variance** — reasoning model, observed ~15-25s with photo. Mitigation: spinner copy, mock fallback via env var if the API degrades mid-demo.
- **API quota/balance** — live test consumed tokens fine; if a 401/429 appears at the venue, flip `FMC_AI_PROVIDER=mock` and say the model is in degraded mode (the UI labels the provider honestly).
- **GPS accuracy indoors** — recorded on the ticket (`accuracy` field); coarse fixes still route to nearest zone. Acceptable.
- **Open question:** do judges expect a map? Current dashboard is a list (no map tiles — avoids live-API fragility). If time remains AFTER Task 7, consider a static SVG zone map; not before.

## Explicitly out of scope (per hackathon constraints)

Auth, user accounts, production DB, queues, vector search, RAG, agents, maps SDK, live traffic/weather APIs, deployment/Docker, OpenAI/Anthropic/Gemini providers.
