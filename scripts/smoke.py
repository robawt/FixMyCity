"""Golden-path smoke test: health -> report -> duplicate grouping -> incidents -> status.
Usage: uv run python scripts/smoke.py [port]"""
import json
import sys
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8000"
BASE = "http://127.0.0.1:" + PORT
fails = []


def check(name, cond, info=""):
    print(("PASS" if cond else "FAIL"), name, info)
    if not cond:
        fails.append(name)


def post_report(text, lat, lng):
    boundary = "X" * 16
    fields = {"text": text, "lat": str(lat), "lng": str(lng), "accuracy": "10"}
    body = b""
    for k, v in fields.items():
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (boundary, k, v)).encode()
    body += ("--%s--\r\n" % boundary).encode()
    req = urllib.request.Request(BASE + "/api/reports", data=body,
                                 headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    return json.load(urllib.request.urlopen(req, timeout=30))


h = json.load(urllib.request.urlopen(BASE + "/api/health", timeout=10))
check("health", h.get("ok"), "provider=%s" % h.get("ai_provider"))

t1 = post_report("Water leaking from a broken pipe near the bus stop, road getting flooded",
                 17.4400, 78.3489)
check("report accepted", t1.get("incident_id") is not None)
check("issue classified", t1.get("issue_type") in ("water_leak", "flooding"), t1.get("issue_type"))
check("urgency in range", 1 <= t1.get("urgency", 0) <= 5, "urgency=%s" % t1.get("urgency"))
check("owner routed", bool(t1.get("service_owner")), t1.get("service_owner"))
check("synthetic label", "SYNTHETIC" in t1.get("context_label", ""))

t2 = post_report("Pipe still leaking, more water now", 17.44005, 78.34895)
check("duplicate grouped", t2.get("duplicate_of") == t1.get("incident_id"),
      "incident=%s dup_of=%s" % (t2.get("incident_id"), t2.get("duplicate_of")))
check("report_count=2", t2.get("report_count") == 2)

inc = json.load(urllib.request.urlopen(BASE + "/api/incidents", timeout=10))["incidents"]
check("incidents listed (seed + live)", len(inc) >= 8, "%d incidents" % len(inc))
check("seed separated", any(i["source"] == "seed" for i in inc) and
      any(i["source"] == "live" for i in inc))

req = urllib.request.Request(BASE + "/api/incidents/%s/status" % t1["incident_id"],
                             data=json.dumps({"status": "in_progress"}).encode(),
                             headers={"Content-Type": "application/json"}, method="PATCH")
ok = json.load(urllib.request.urlopen(req, timeout=10)).get("ok")
check("status patch", ok)

for page in ("/", "/admin"):
    r = urllib.request.urlopen(BASE + page, timeout=10)
    check("page %s loads" % page, r.status == 200 and b"FixMyCity" in r.read())

print("\n%d checks failed" % len(fails) if fails else "\nALL CHECKS PASSED")
sys.exit(1 if fails else 0)
