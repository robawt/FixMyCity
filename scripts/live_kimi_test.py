"""One live end-to-end test through the real Kimi API: text + photo report.
Generates a synthetic 'pothole-like' PNG, POSTs it, prints the ticket.
Usage: uv run python scripts/live_kimi_test.py [port]"""
import json
import os
import subprocess
import sys
import zlib
import struct

PORT = sys.argv[1] if len(sys.argv) > 1 else "8000"


def png(w, h, px):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"".join(bytes(px(x, y)) for x in range(w)) for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def px(x, y):
    dx, dy = (x - 64) / 40.0, (y - 32) / 18.0
    if dx * dx + dy * dy < 1.0:
        return (35, 32, 30)          # dark elliptical hole
    return (120 + (x * 7 + y * 13) % 15,) * 3   # gray road texture


path = os.path.join(os.path.dirname(__file__), "_test.png")
open(path, "wb").write(png(128, 64, px))

r = subprocess.run([
    "curl", "-s", "--max-time", "150", "-X", "POST",
    "http://127.0.0.1:" + PORT + "/api/reports",
    "-F", "text=Large pothole in the middle of the road near Gachibowli, two-wheelers swerving to avoid it",
    "-F", "photo=@" + path + ";type=image/png",
    "-F", "lat=17.4401", "-F", "lng=78.3490", "-F", "accuracy=8"],
    capture_output=True, text=True, timeout=180)

if r.returncode != 0:
    print("CURL FAILED:", r.stderr[:300])
    sys.exit(1)
d = json.loads(r.stdout)
keys = ("incident_id", "issue_type", "service_owner", "urgency", "confidence",
        "review_flag", "verification", "summary", "observed", "claimed",
        "severity_reasons", "ai_provider")
print(json.dumps({k: d.get(k) for k in keys}, indent=1))
