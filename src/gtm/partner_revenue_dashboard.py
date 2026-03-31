"""Partner-attributed revenue tracking dashboard
FastAPI service — OCI Robot Cloud
Port: 10153"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10153

# ── Static revenue data ─────────────────────────────────────────────────────
_PARTNER_DATA = {
    "nvidia": {
        "name": "NVIDIA",
        "type": "technology",
        "attributed_arr": 87_500,          # $87.5K referral
        "direct_arr": 162_500,             # $162.5K direct
        "total_arr": 250_000,
        "arr_share_pct": 35.0,             # 35% of ARR
        "pipeline": 420_000,               # $420K attributed pipeline
        "pipeline_share_pct": 35.0,        # 35% of $1.2M
        "investment_hours": 40,
        "roi": 2187,                       # 2,187:1 ROI
        "roi_label": "2,187:1",
        "next_milestone": "Co-sell agreement Q2 2026",
        "trend": "+12% MoM",
    },
}

_TOTAL_ARR = 250_000
_TOTAL_PIPELINE = 1_200_000


def _get_partner_revenue(partner_type: str | None, period: str | None) -> dict:
    partners = [
        {
            "partner": k,
            **{kk: vv for kk, vv in v.items()}
        }
        for k, v in _PARTNER_DATA.items()
        if (partner_type is None or v["type"] == partner_type)
    ]

    period_label = period or "current_quarter"
    for p in partners:
        p["period"] = period_label

    return {
        "partner_type_filter": partner_type or "all",
        "period": period_label,
        "partners": partners,
        "summary": {
            "total_attributed_arr": sum(p["attributed_arr"] for p in partners),
            "total_pipeline": sum(p["pipeline"] for p in partners),
            "total_arr": _TOTAL_ARR,
            "total_pipeline_base": _TOTAL_PIPELINE,
        },
        "ts": datetime.utcnow().isoformat(),
    }


def _get_dashboard() -> dict:
    all_partners = list(_PARTNER_DATA.values())
    total_attributed = sum(p["attributed_arr"] for p in all_partners)
    total_pipeline = sum(p["pipeline"] for p in all_partners)

    top_partner = max(all_partners, key=lambda p: p["attributed_arr"])

    return {
        "all_partners": [
            {
                "name": p["name"],
                "type": p["type"],
                "attributed_arr": p["attributed_arr"],
                "arr_share_pct": p["arr_share_pct"],
                "pipeline": p["pipeline"],
                "pipeline_share_pct": p["pipeline_share_pct"],
                "roi": p["roi"],
                "roi_label": p["roi_label"],
                "investment_hours": p["investment_hours"],
                "trend": p["trend"],
                "next_milestone": p["next_milestone"],
            }
            for p in all_partners
        ],
        "totals": {
            "total_attributed_arr": total_attributed,
            "direct_arr": _TOTAL_ARR - total_attributed,
            "total_arr": _TOTAL_ARR,
            "attributed_share_pct": round(total_attributed / _TOTAL_ARR * 100, 1),
            "total_attributed_pipeline": total_pipeline,
            "total_pipeline_base": _TOTAL_PIPELINE,
            "pipeline_attributed_share_pct": round(total_pipeline / _TOTAL_PIPELINE * 100, 1),
        },
        "top_partner": {
            "name": top_partner["name"],
            "attributed_arr": top_partner["attributed_arr"],
            "roi_label": top_partner["roi_label"],
        },
        "next_milestone": top_partner["next_milestone"],
        "ts": datetime.utcnow().isoformat(),
    }


if USE_FASTAPI:
    app = FastAPI(title="Partner Revenue Dashboard", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Partner Revenue Dashboard</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Partner Revenue Dashboard</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>NVIDIA referral $87.5K (35% ARR) · ROI 2,187:1 · $420K pipeline</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/partners/revenue")
    def partner_revenue(
        partner_type: str = Query(None, description="Filter by partner type (e.g. 'technology')"),
        period: str = Query(None, description="Time period label (e.g. 'Q1_2026')"),
    ):
        """
        Partner-attributed revenue by type and period.
        Returns attributed_arr, pipeline, roi, and trend per partner.
        """
        return JSONResponse(content=_get_partner_revenue(partner_type, period))

    @app.get("/partners/dashboard")
    def partners_dashboard():
        """
        Full partner dashboard: all partners, totals, top partner, and next milestone.
        NVIDIA: $87.5K attributed ARR (35%), $420K pipeline (35% of $1.2M), ROI 2,187:1.
        """
        return JSONResponse(content=_get_dashboard())

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())

        def log_message(self, *a):
            pass

    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
