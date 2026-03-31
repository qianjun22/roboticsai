"""
Systematic CAC reduction engine — tactic-level CAC breakdown, lever analysis, blended CAC roadmap toward $8K at AI World.
FastAPI service — OCI Robot Cloud
Port: 10097
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

try:
    from fastapi import FastAPI, Query, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10097

# ---------------------------------------------------------------------------
# Domain data — channel-level CAC breakdown
# ---------------------------------------------------------------------------
# All costs in USD.  Figures derived from Q1 2026 GTM analysis.

CHANNEL_DATA: Dict[str, Dict[str, Any]] = {
    "nvidia_referral": {
        "display_name": "NVIDIA Referral",
        "cac": 6_000,
        "conversion_rate": 0.22,      # 22% of qualified leads close
        "avg_deal_size": 180_000,
        "monthly_volume": 4,           # new customers / month
        "source": "partner",
        "optimization_opportunity": "Expand to 3 more NVIDIA field reps; expected +6 leads/mo",
        "time_to_close_days": 42,
        "notes": "Highest-quality intent; joint solution demos drive conversion",
    },
    "outbound_sdr": {
        "display_name": "Outbound SDR",
        "cac": 14_000,
        "conversion_rate": 0.08,
        "avg_deal_size": 150_000,
        "monthly_volume": 3,
        "source": "outbound",
        "optimization_opportunity": "Persona-targeted sequences cut CAC to ~$10K; reduce SDR seats by 1",
        "time_to_close_days": 68,
        "notes": "High volume but low intent; best for mid-market manufacturing verticals",
    },
    "ai_world_event": {
        "display_name": "AI World Conference",
        "cac": 9_500,
        "conversion_rate": 0.17,
        "avg_deal_size": 200_000,
        "monthly_volume": 2,
        "source": "event",
        "optimization_opportunity": "Live demo booth increases conversion by ~30%; target $8K CAC",
        "time_to_close_days": 55,
        "notes": "Strong for enterprise; GR00T live demo is key differentiator",
    },
    "inbound_content": {
        "display_name": "Inbound / Content",
        "cac": 7_200,
        "conversion_rate": 0.12,
        "avg_deal_size": 140_000,
        "monthly_volume": 2,
        "source": "inbound",
        "optimization_opportunity": "SEO + CoRL paper distribution expected +1.5 leads/mo at flat cost",
        "time_to_close_days": 50,
        "notes": "Growing channel; CoRL paper drives qualified academic + enterprise leads",
    },
    "oracle_field": {
        "display_name": "Oracle Field Sales Co-Sell",
        "cac": 5_500,
        "conversion_rate": 0.25,
        "avg_deal_size": 220_000,
        "monthly_volume": 3,
        "source": "partner",
        "optimization_opportunity": "Dedicated OCI robotics SKU accelerates deal registration; +2 deals/mo",
        "time_to_close_days": 38,
        "notes": "Best CAC channel; limited by # of trained field reps",
    },
    "design_partner_crm": {
        "display_name": "Design Partner CRM Pipeline",
        "cac": 3_800,
        "conversion_rate": 0.40,
        "avg_deal_size": 160_000,
        "monthly_volume": 2,
        "source": "direct",
        "optimization_opportunity": "Structured beta→GA conversion playbook; target $3K CAC in H2",
        "time_to_close_days": 30,
        "notes": "Lowest CAC; design partners already have product experience",
    },
}

# Blended CAC roadmap milestones (quarter, target_cac, primary_lever)
ROADMAP_MILESTONES = [
    {"quarter": "Q1 2026", "target_cac": 11_000, "achieved": True,
     "primary_lever": "Baseline measurement + channel attribution"},
    {"quarter": "Q2 2026", "target_cac": 10_000, "achieved": False,
     "primary_lever": "NVIDIA referral expansion + SDR sequence optimisation"},
    {"quarter": "Q3 2026", "target_cac": 9_000, "achieved": False,
     "primary_lever": "Oracle co-sell SKU launch + content inbound scale"},
    {"quarter": "AI World (Oct 2026)", "target_cac": 8_000, "achieved": False,
     "primary_lever": "Live GR00T demo booth + design-partner conversion playbook"},
    {"quarter": "Q4 2026", "target_cac": 7_500, "achieved": False,
     "primary_lever": "Flywheel: inbound + referral compound at scale"},
]

# Levers with estimated CAC impact
LEVERS = [
    {"lever": "NVIDIA referral program expansion",
     "cac_reduction": 800, "effort": "medium", "timeline_weeks": 6},
    {"lever": "SDR persona targeting + sequence A/B test",
     "cac_reduction": 2_200, "effort": "medium", "timeline_weeks": 8},
    {"lever": "Oracle field co-sell SKU",
     "cac_reduction": 1_500, "effort": "high", "timeline_weeks": 12},
    {"lever": "CoRL paper inbound distribution",
     "cac_reduction": 600, "effort": "low", "timeline_weeks": 2},
    {"lever": "Design partner → GA conversion playbook",
     "cac_reduction": 1_000, "effort": "low", "timeline_weeks": 4},
    {"lever": "AI World live demo booth",
     "cac_reduction": 1_200, "effort": "high", "timeline_weeks": 16},
]

CURRENT_BLENDED_CAC = 10_200  # weighted average across all channels, Q1 2026

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def blended_cac(channel_mix: Optional[Dict[str, float]] = None) -> float:
    """Compute volume-weighted blended CAC across all channels (or a custom mix)."""
    if channel_mix is None:
        channel_mix = {k: v["monthly_volume"] for k, v in CHANNEL_DATA.items()}

    total_volume = sum(channel_mix.values())
    if total_volume == 0:
        return 0.0

    weighted = sum(
        CHANNEL_DATA[ch]["cac"] * vol
        for ch, vol in channel_mix.items()
        if ch in CHANNEL_DATA
    )
    return round(weighted / total_volume, 2)


def project_cac(target_date_str: str) -> Dict[str, Any]:
    """Project blended CAC at a future date based on roadmap trajectory."""
    # Map milestone quarters to approximate dates for interpolation
    milestone_map = {
        "Q1 2026": datetime(2026, 3, 31),
        "Q2 2026": datetime(2026, 6, 30),
        "Q3 2026": datetime(2026, 9, 30),
        "AI World (Oct 2026)": datetime(2026, 10, 31),
        "Q4 2026": datetime(2026, 12, 31),
    }

    try:
        target_dt = datetime.fromisoformat(target_date_str)
    except ValueError:
        raise ValueError(f"Invalid date format: {target_date_str}. Use ISO 8601 (YYYY-MM-DD).")

    # Find bracketing milestones
    dates = sorted(milestone_map.items(), key=lambda x: x[1])
    start_cac = CURRENT_BLENDED_CAC
    start_dt = datetime(2026, 1, 1)

    projected_cac = start_cac
    for quarter, dt in dates:
        ms = next(m for m in ROADMAP_MILESTONES if m["quarter"] == quarter)
        if target_dt <= dt:
            # Interpolate linearly
            span = (dt - start_dt).days or 1
            elapsed = (target_dt - start_dt).days
            frac = max(0.0, min(1.0, elapsed / span))
            projected_cac = start_cac - frac * (start_cac - ms["target_cac"])
            break
        start_cac = ms["target_cac"]
        start_dt = dt
        projected_cac = ms["target_cac"]

    # Required initiatives: levers not yet at this horizon
    required = [
        lv["lever"] for lv in LEVERS
        if (target_dt - datetime.utcnow()).days >= lv["timeline_weeks"] * 7
    ]

    return {
        "target_date": target_date_str,
        "projected_cac": round(projected_cac, 0),
        "current_blended_cac": CURRENT_BLENDED_CAC,
        "delta": round(CURRENT_BLENDED_CAC - projected_cac, 0),
        "required_initiatives": required,
        "roadmap_milestones": ROADMAP_MILESTONES,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="CAC Reduction Engine",
        version="1.0.0",
        description=(
            "Tactic-level CAC breakdown (NVIDIA referral $6K vs outbound $14K), "
            "lever analysis, blended CAC roadmap targeting $8K at AI World."
        ),
    )

    @app.get("/gtm/cac_analysis")
    def cac_analysis(channel: Optional[str] = Query(default=None, description="Channel key, e.g. nvidia_referral")):
        """Return CAC metrics for a specific channel, or all channels if omitted."""
        if channel:
            if channel not in CHANNEL_DATA:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown channel '{channel}'. Valid: {list(CHANNEL_DATA.keys())}",
                )
            data = CHANNEL_DATA[channel].copy()
            data["channel_key"] = channel
            data["roi_multiple"] = round(data["avg_deal_size"] / data["cac"], 2)
            return {"channel": data, "blended_cac": blended_cac(), "ts": datetime.utcnow().isoformat()}

        # All channels
        enriched = {}
        for k, v in CHANNEL_DATA.items():
            entry = v.copy()
            entry["channel_key"] = k
            entry["roi_multiple"] = round(v["avg_deal_size"] / v["cac"], 2)
            enriched[k] = entry

        # Sort by CAC ascending (best first)
        sorted_channels = dict(sorted(enriched.items(), key=lambda x: x[1]["cac"]))

        return {
            "channels": sorted_channels,
            "blended_cac": blended_cac(),
            "best_channel": min(CHANNEL_DATA, key=lambda k: CHANNEL_DATA[k]["cac"]),
            "worst_channel": max(CHANNEL_DATA, key=lambda k: CHANNEL_DATA[k]["cac"]),
            "levers": LEVERS,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/gtm/cac_roadmap")
    def cac_roadmap(
        target_date: str = Query(
            default="2026-10-31",
            description="ISO 8601 date to project CAC toward (e.g. 2026-10-31 for AI World)",
        )
    ):
        """Project blended CAC at a future date and return the required initiatives."""
        try:
            result = project_cac(target_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        result["ts"] = datetime.utcnow().isoformat()
        return result

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "cac_reduction_engine",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        channel_rows = "".join(
            f"<tr><td>{v['display_name']}</td>"
            f"<td>${v['cac']:,}</td>"
            f"<td>{int(v['conversion_rate']*100)}%</td>"
            f"<td>{v['monthly_volume']}</td></tr>"
            for v in CHANNEL_DATA.values()
        )
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>CAC Reduction Engine</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}
h1{{color:#C74634}}a{{color:#38bdf8}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:.5rem 1rem;text-align:left;border-bottom:1px solid #334155}}
th{{color:#94a3b8}}
.stat{{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}}</style></head><body>
<h1>CAC Reduction Engine</h1><p>OCI Robot Cloud · Port 10097</p>
<div>
  <span class="stat">Current Blended CAC: ${CURRENT_BLENDED_CAC:,}</span>
  <span class="stat">AI World Target: $8,000</span>
  <span class="stat">Best Channel: Design Partner CRM ($3,800)</span>
</div>
<h2>Channel Breakdown</h2>
<table><tr><th>Channel</th><th>CAC</th><th>Conv. Rate</th><th>Vol/mo</th></tr>
{channel_rows}</table>
<p><a href="/docs">API Docs</a> | <a href="/gtm/cac_analysis">CAC Analysis</a> | <a href="/gtm/cac_roadmap">Roadmap</a> | <a href="/health">Health</a></p>
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
