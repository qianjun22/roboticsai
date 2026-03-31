"""
AI World September 2026 sponsorship management — Oracle $150K booth + NVIDIA co-sponsorship tracking.
FastAPI service — OCI Robot Cloud
Port: 10101
"""
from __future__ import annotations
import json, random, time
from datetime import datetime, date
from typing import Dict, List, Optional, Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10101

# ── Domain data ───────────────────────────────────────────────────────────────
EVENT_META = {
    "name": "AI World 2026",
    "dates": "September 14-16, 2026",
    "venue": "Boston Convention & Exhibition Center, Boston MA",
    "expected_attendees": 8500,
    "expected_reach": 42000,  # social + press amplification
    "tracks": ["Robotics & Automation", "LLM & Agents", "Edge AI", "AI Infrastructure", "Enterprise AI"],
}

SPONSORS: Dict[str, Dict] = {
    "oracle": {
        "tier": "platinum",
        "commitment_usd": 150000,
        "status": "confirmed",
        "signed_date": "2026-02-10",
        "contacts": [
            {"name": "Jun Qian", "role": "Technical Lead", "email": "jun.qian@oracle.com"},
            {"name": "Sarah Chen", "role": "Events Marketing", "email": "sarah.chen@oracle.com"},
        ],
        "deliverables": [
            "40x40 ft main booth (Hall A, premium location)",
            "3× keynote speaking slots (30 min each)",
            "Logo on all event materials + website",
            "8× VIP dinner seats (Sep 14 evening)",
            "Full-page ad in event program",
            "20× full-access passes",
            "Lead retrieval system access",
        ],
        "timeline": [
            {"milestone": "Contract signed", "date": "2026-02-10", "status": "done"},
            {"milestone": "Booth design approved", "date": "2026-04-15", "status": "in_progress"},
            {"milestone": "Speaking topics confirmed", "date": "2026-05-01", "status": "pending"},
            {"milestone": "Demo hardware shipped", "date": "2026-08-25", "status": "pending"},
            {"milestone": "Staff travel booked", "date": "2026-07-31", "status": "pending"},
            {"milestone": "Event opens", "date": "2026-09-14", "status": "pending"},
        ],
        "notes": "Co-marketing with NVIDIA on OCI Robot Cloud + Isaac Sim integration story.",
    },
    "nvidia": {
        "tier": "gold",
        "commitment_usd": 75000,
        "status": "in_negotiation",
        "signed_date": None,
        "contacts": [
            {"name": "Alex Park", "role": "Robotics BizDev", "email": "apark@nvidia.com"},
        ],
        "deliverables": [
            "20x20 ft co-branded demo area adjacent to Oracle booth",
            "1× keynote speaking slot (20 min)",
            "Joint press release on OCI + Isaac Sim partnership",
            "10× full-access passes",
            "Logo on Oracle booth digital displays",
        ],
        "timeline": [
            {"milestone": "MOU signed", "date": "2026-03-28", "status": "in_progress"},
            {"milestone": "Joint press release drafted", "date": "2026-05-15", "status": "pending"},
            {"milestone": "Co-branded materials ready", "date": "2026-08-01", "status": "pending"},
            {"milestone": "Event opens", "date": "2026-09-14", "status": "pending"},
        ],
        "notes": "Negotiating joint GR00T + OCI demo at booth. GPU credits as part of co-marketing deal.",
    },
    "boston_dynamics": {
        "tier": "silver",
        "commitment_usd": 35000,
        "status": "prospect",
        "signed_date": None,
        "contacts": [
            {"name": "Maya Robinson", "role": "Partnerships", "email": "mrobinson@bostondynamics.com"},
        ],
        "deliverables": [
            "10x10 ft demo pod",
            "1× panel participation slot",
            "5× full-access passes",
        ],
        "timeline": [
            {"milestone": "Initial outreach", "date": "2026-03-15", "status": "done"},
            {"milestone": "Proposal sent", "date": "2026-04-01", "status": "pending"},
        ],
        "notes": "Stretch goal — Spot robot live demo at Oracle booth would be flagship moment.",
    },
}

BOOTH_PLAN = {
    "layout": {
        "total_sqft": 1600,
        "zones": [
            {"zone": "Welcome & Branding", "sqft": 200, "elements": ["LED video wall 12ft", "Oracle red branding arch"]},
            {"zone": "OCI Robot Cloud Live Demo", "sqft": 400, "elements": ["3x robot arms (GR00T N1.6)", "Isaac Sim display wall", "Bimanual task demo station"]},
            {"zone": "NVIDIA Co-Demo Area", "sqft": 400, "elements": ["Jetson Orin edge node", "GR00T inference bench", "Joint OCI+NVIDIA banners"]},
            {"zone": "Customer Briefing Room", "sqft": 300, "elements": ["8-seat conference table", "Pitch screen", "NDA signing station"]},
            {"zone": "Lounge & Lead Capture", "sqft": 300, "elements": ["Barista station", "Badge scan kiosks", "Merch display"]},
        ],
    },
    "staffing": [
        {"role": "Technical Lead", "count": 2, "owner": "Oracle Robotics Eng"},
        {"role": "Solutions Engineer", "count": 4, "owner": "Oracle SE team"},
        {"role": "Executive Sponsor", "count": 1, "owner": "VP Engineering"},
        {"role": "Marketing & Events", "count": 2, "owner": "Oracle Marketing"},
        {"role": "NVIDIA Partner Staff", "count": 2, "owner": "NVIDIA"},
        {"role": "AV / Logistics", "count": 2, "owner": "Events vendor"},
    ],
    "demo_schedule": [
        {"time": "09:00", "demo": "GR00T bimanual lift demo", "duration_min": 15, "presenter": "Technical Lead"},
        {"time": "10:00", "demo": "OCI Robot Cloud pipeline walkthrough", "duration_min": 20, "presenter": "Solutions Engineer"},
        {"time": "11:00", "demo": "Isaac Sim SDG + fine-tune live", "duration_min": 20, "presenter": "Technical Lead"},
        {"time": "13:00", "demo": "GR00T bimanual lift demo", "duration_min": 15, "presenter": "Technical Lead"},
        {"time": "14:00", "demo": "Jetson edge deploy + latency benchmark", "duration_min": 15, "presenter": "NVIDIA Partner Staff"},
        {"time": "15:30", "demo": "Customer use-case: warehouse automation", "duration_min": 25, "presenter": "Solutions Engineer"},
        {"time": "17:00", "demo": "Closing keynote teaser + CTA", "duration_min": 10, "presenter": "Executive Sponsor"},
    ],
}


def _days_until(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    try:
        target = date.fromisoformat(date_str)
        return (target - date.today()).days
    except ValueError:
        return None


# ── FastAPI app ───────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="AI World Sponsor Outreach", version="1.0.0")

    @app.get("/events/ai_world/sponsorship")
    def get_sponsorship(
        sponsor_type: Optional[str] = Query(
            None,
            description="Filter by sponsor key: oracle | nvidia | boston_dynamics",
        )
    ):
        """Return sponsorship deliverables, timeline, contacts, and status."""
        catalog = SPONSORS
        if sponsor_type:
            if sponsor_type not in catalog:
                raise HTTPException(
                    status_code=404,
                    detail=f"Sponsor '{sponsor_type}' not found. Available: {list(catalog.keys())}",
                )
            catalog = {sponsor_type: catalog[sponsor_type]}

        result: Dict[str, Any] = {"event": EVENT_META, "sponsors": {}}
        total_committed = 0
        for key, info in catalog.items():
            days = _days_until(info["timeline"][-1]["date"] if info["timeline"] else None)
            entry = dict(info)
            entry["days_to_event"] = days
            result["sponsors"][key] = entry
            if info["status"] in ("confirmed", "in_negotiation"):
                total_committed += info["commitment_usd"]

        result["summary"] = {
            "confirmed_sponsors": sum(1 for v in catalog.values() if v["status"] == "confirmed"),
            "total_committed_usd": total_committed,
            "days_to_event": _days_until("2026-09-14"),
        }
        return result

    @app.get("/events/ai_world/booth_plan")
    def get_booth_plan():
        """Return booth layout, demo schedule, and staffing plan."""
        return {
            "event": EVENT_META,
            "booth": BOOTH_PLAN,
            "metrics": {
                "total_demos_per_day": len(BOOTH_PLAN["demo_schedule"]),
                "total_staff": sum(s["count"] for s in BOOTH_PLAN["staffing"]),
                "booth_sqft": BOOTH_PLAN["layout"]["total_sqft"],
                "zones": len(BOOTH_PLAN["layout"]["zones"]),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        confirmed = sum(1 for v in SPONSORS.values() if v["status"] == "confirmed")
        total_usd = sum(
            v["commitment_usd"] for v in SPONSORS.values()
            if v["status"] in ("confirmed", "in_negotiation")
        )
        return {
            "status": "ok",
            "service": "ai_world_sponsor_outreach",
            "port": PORT,
            "event": "AI World 2026 (Sep 14-16)",
            "sponsors_confirmed": confirmed,
            "total_committed_usd": total_usd,
            "days_to_event": _days_until("2026-09-14"),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""
<!DOCTYPE html><html><head><title>AI World Sponsor Outreach</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
table{border-collapse:collapse;margin-top:1rem}td,th{border:1px solid #334155;padding:.5rem 1rem;text-align:left}
th{background:#1e293b}.confirmed{color:#4ade80}.pending{color:#facc15}.prospect{color:#94a3b8}</style></head><body>
<h1>AI World Sponsor Outreach</h1>
<p>OCI Robot Cloud &middot; Port 10101 &middot; AI World Sep 14-16, 2026 &middot; Boston BCEC</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/events/ai_world/sponsorship">Sponsorships</a> | <a href="/events/ai_world/booth_plan">Booth Plan</a></p>
<div class="stat">Oracle Booth: <strong>$150K</strong></div>
<div class="stat">NVIDIA Co-sponsor: <strong>$75K</strong></div>
<div class="stat">Expected Attendees: <strong>8,500</strong></div>
<div class="stat">Total Reach: <strong>42,000</strong></div>
<h2>Sponsor Status</h2>
<table><tr><th>Sponsor</th><th>Tier</th><th>Commitment</th><th>Status</th></tr>
<tr><td>Oracle</td><td>Platinum</td><td>$150,000</td><td class="confirmed">Confirmed</td></tr>
<tr><td>NVIDIA</td><td>Gold</td><td>$75,000</td><td class="pending">In Negotiation</td></tr>
<tr><td>Boston Dynamics</td><td>Silver</td><td>$35,000</td><td class="prospect">Prospect</td></tr>
</table>
</body></html>""")

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
