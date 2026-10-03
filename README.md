# FixMyCity MVP

Hyderabad civic-AI hackathon demo: citizen report -> AI evidence extraction (Kimi K3, vision) -> policy severity -> routing -> structured ticket -> admin dashboard.

## Run

```bash
uv sync
uv run python -m server.seed          # one-time: 7 synthetic demo incidents
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
```

- Citizen page: http://127.0.0.1:8000/  (QR flow: add ?site=SITE_ID)
- Admin dashboard: http://127.0.0.1:8000/admin
- Phone demo (same Wi-Fi): use the LAN IP, e.g. http://192.168.0.22:8000/

## Demo day

```bash
uv run python scripts/reset_demo.py             # restore to pristine seeded state (IDs 1-7)
uv run python scripts/make_qr.py "http://<LAN-IP>:8000/?site=HACKATHON-BOOTH-1"
```

QR is written to docs/demo-qr.svg — open it in a browser and let judges scan it.
If the venue Wi-Fi has client isolation (phone can't reach laptop), run the demo
on the laptop browser, or serve from a laptop hotspot.

## Config (.env, never commit)

- KIMI_API_KEY — Kimi Open Platform key (api.moonshot.ai). Absent -> mock provider.
- KIMI_MODEL — default kimi-k3 (vision-capable).
- FMC_AI_PROVIDER — auto | kimi | mock. auto = kimi if key present else mock.

Kimi quirks: models require temperature=1 (param omitted); kimi-k3 is a reasoning
model — max_tokens must be >=1500 or responses come back empty.

## Test

```bash
uv run python scripts/smoke.py 8000          # golden path (fast, any provider)
uv run python scripts/live_kimi_test.py 8000 # one real Kimi text+photo call
```

## Data integrity

- source='live' rows: real submissions. source='seed' rows: synthetic demo data.
- All context (traffic/weather/hotspots/jurisdiction) is SYNTHETIC — labeled in API responses.
- AI extracts evidence only; severity/urgency is computed by server/severity.py policy code.
