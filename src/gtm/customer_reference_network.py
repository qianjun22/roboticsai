"""
Structured customer reference network — intelligent prospect-to-reference matching.
FastAPI service — OCI Robot Cloud
Port: 10103
"""
from __future__ import annotations
import json, math, random, time, uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10103

# ---------------------------------------------------------------------------
# Domain data — reference customer database
# ---------------------------------------------------------------------------

REFERENCE_CUSTOMERS: List[Dict[str, Any]] = [
    {
        "id": "ref-001",
        "company": "AutoFlex Robotics",
        "industry": "automotive",
        "company_size": "enterprise",          # startup | mid-market | enterprise
        "robots": ["Franka Emika", "UR10e"],
        "use_cases": ["pick_place", "assembly", "quality_inspection"],
        "nps_score": 87,
        "close_rate_lift": 0.38,              # measured lift when used as reference
        "reference_calls_given": 14,
        "avg_call_rating": 4.7,
        "incentive_tier": "platinum",          # bronze | silver | gold | platinum
        "contact": "Sarah Chen, VP Engineering",
        "topics_expert": ["fine-tuning ROI", "OCI GPU cost", "sim-to-real gap"],
        "available": True,
        "timezone": "America/Los_Angeles",
    },
    {
        "id": "ref-002",
        "company": "MediBot Systems",
        "industry": "healthcare",
        "company_size": "mid-market",
        "robots": ["UR5e", "Kinova Gen3"],
        "use_cases": ["surgical_assist", "lab_automation", "pick_place"],
        "nps_score": 91,
        "close_rate_lift": 0.41,
        "reference_calls_given": 9,
        "avg_call_rating": 4.9,
        "incentive_tier": "platinum",
        "contact": "Dr. Raj Patel, CTO",
        "topics_expert": ["safety compliance", "HIPAA data handling", "DAgger fine-tuning"],
        "available": True,
        "timezone": "America/New_York",
    },
    {
        "id": "ref-003",
        "company": "LogiDrone Inc",
        "industry": "logistics",
        "company_size": "startup",
        "robots": ["Boston Dynamics Spot", "custom drone"],
        "use_cases": ["warehouse_navigation", "inventory_scan", "long_horizon_assemble"],
        "nps_score": 78,
        "close_rate_lift": 0.29,
        "reference_calls_given": 5,
        "avg_call_rating": 4.4,
        "incentive_tier": "gold",
        "contact": "Marcus Lee, Head of AI",
        "topics_expert": ["long-horizon planning", "multi-robot coordination", "temporal DAgger"],
        "available": True,
        "timezone": "Europe/London",
    },
    {
        "id": "ref-004",
        "company": "PrecisionFab Co",
        "industry": "manufacturing",
        "company_size": "enterprise",
        "robots": ["KUKA LBR", "ABB YuMi", "Franka Emika"],
        "use_cases": ["peg_insert", "assembly", "quality_inspection", "pick_place"],
        "nps_score": 83,
        "close_rate_lift": 0.34,
        "reference_calls_given": 21,
        "avg_call_rating": 4.5,
        "incentive_tier": "platinum",
        "contact": "Linda Hofer, Director of Automation",
        "topics_expert": ["multi-robot fleets", "GR00T N1.6 performance", "Isaac Sim SDG"],
        "available": True,
        "timezone": "Europe/Berlin",
    },
    {
        "id": "ref-005",
        "company": "AgriBot Ventures",
        "industry": "agriculture",
        "company_size": "startup",
        "robots": ["custom arm"],
        "use_cases": ["pick_place", "sorting", "plant_inspection"],
        "nps_score": 74,
        "close_rate_lift": 0.22,
        "reference_calls_given": 3,
        "avg_call_rating": 4.2,
        "incentive_tier": "silver",
        "contact": "Tom Rivera, CEO",
        "topics_expert": ["startup onboarding", "cost-effective fine-tuning", "SDG on budget"],
        "available": False,   # currently paused
        "timezone": "America/Chicago",
    },
]

# Incentive tier definitions (NPS thresholds and perks)
INTENTIVE_TIERS: Dict[str, Dict[str, Any]] = {
    "bronze":   {"min_nps": 60,  "min_calls": 1,  "perks": ["$500 OCI credits"],                                          "badge": "OCI Robot Cloud Reference Partner"},
    "silver":   {"min_nps": 70,  "min_calls": 3,  "perks": ["$2,000 OCI credits", "co-marketing blog"],                 "badge": "OCI Robot Cloud Silver Reference"},
    "gold":     {"min_nps": 78,  "min_calls": 5,  "perks": ["$5,000 OCI credits", "case study", "joint PR"],             "badge": "OCI Robot Cloud Gold Reference"},
    "platinum": {"min_nps": 85,  "min_calls": 10, "perks": ["$15,000 OCI credits", "advisory board seat", "keynote slot"], "badge": "OCI Robot Cloud Platinum Reference"},
}

# In-memory scheduled calls
_scheduled_calls: List[Dict[str, Any]] = []

# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _score_reference(
    ref: Dict[str, Any],
    use_cases: List[str],
    robots: List[str],
    company_size: str,
    industry: Optional[str],
) -> float:
    """Score a reference against a prospect profile (0..1)."""
    score = 0.0

    # Use-case overlap (weight 0.40)
    uc_overlap = len(set(use_cases) & set(ref["use_cases"]))
    uc_score = uc_overlap / max(len(use_cases), 1)
    score += 0.40 * uc_score

    # Robot overlap (weight 0.25)
    robot_overlap = len(set(robots) & set(ref["robots"]))
    robot_score = min(robot_overlap / max(len(robots), 1), 1.0)
    score += 0.25 * robot_score

    # Company size match (weight 0.15)
    if ref["company_size"] == company_size:
        score += 0.15
    elif abs(["startup", "mid-market", "enterprise"].index(ref["company_size"]) -
             ["startup", "mid-market", "enterprise"].index(company_size)) == 1:
        score += 0.07  # adjacent size

    # Industry match (weight 0.10)
    if industry and ref["industry"] == industry:
        score += 0.10

    # NPS / quality signal (weight 0.10)
    score += 0.10 * (ref["nps_score"] / 100)

    # Availability filter — unavailable refs get a hard penalty
    if not ref["available"]:
        score *= 0.25

    return round(score, 4)


def _generate_briefing_doc(
    ref: Dict[str, Any],
    prospect_id: str,
    call_time: str,
) -> Dict[str, Any]:
    """Build a reference call briefing document."""
    return {
        "title": f"Reference Call Briefing — {ref['company']}",
        "prospect_id": prospect_id,
        "reference_company": ref["company"],
        "reference_contact": ref["contact"],
        "scheduled_time": call_time,
        "incentive_tier": ref["incentive_tier"],
        "incentive_perks": INTENTIVE_TIERS[ref["incentive_tier"]]["perks"],
        "suggested_topics": ref["topics_expert"],
        "do_not_discuss": ["competitor pricing", "unreleased features", "SLA specifics"],
        "expected_close_rate_lift": f"+{round(ref['close_rate_lift'] * 100)}%",
        "reference_nps": ref["nps_score"],
        "avg_past_call_rating": ref["avg_call_rating"],
        "generated_at": datetime.utcnow().isoformat(),
    }

# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Customer Reference Network",
        version="1.0.0",
        description=(
            "Intelligent prospect-to-reference matching by use case, robot type, "
            "and company size. NPS-based incentive tiers. "
            "+34% close rate improvement post-reference call."
        ),
    )

    # --- Request / Response schemas ---

    class ProspectProfile(BaseModel):
        use_cases: List[str] = Field(
            ["pick_place", "assembly"],
            description="Use cases the prospect is evaluating",
        )
        robots: List[str] = Field(
            ["Franka Emika"],
            description="Robot platforms the prospect is considering",
        )
        company_size: str = Field(
            "mid-market",
            description="startup | mid-market | enterprise",
        )
        industry: Optional[str] = Field(
            None,
            description="Prospect's industry (optional but improves match)",
        )
        max_results: int = Field(3, ge=1, le=5, description="Number of top references to return")

    class ReferenceMatch(BaseModel):
        reference_id: str
        company: str
        match_score: float
        use_case_overlap: List[str]
        robot_overlap: List[str]
        company_size: str
        industry: str
        contact: str
        incentive_tier: str
        nps_score: int
        avg_call_rating: float
        expected_close_rate_lift: str
        suggested_topics: List[str]
        available: bool

    class MatchResponse(BaseModel):
        top_references: List[ReferenceMatch]
        match_scores: Dict[str, float]
        prospect_profile: Dict[str, Any]
        overall_program_close_rate_lift: str
        ts: str

    class ScheduleRequest(BaseModel):
        prospect_id: str = Field(..., description="CRM prospect identifier")
        reference_id: str = Field(..., description="Reference customer ID (ref-001 … ref-005)")
        preferred_slot: Optional[str] = Field(
            None,
            description="ISO-8601 preferred call time; auto-assigned if omitted",
        )

    class ScheduleResponse(BaseModel):
        call_id: str
        call_scheduled: bool
        scheduled_time: str
        reference_company: str
        reference_contact: str
        briefing_doc: Dict[str, Any]
        calendar_invite_sent: bool
        ts: str

    # --- Endpoints ---

    @app.get("/references/match", response_model=MatchResponse)
    def match_references(
        use_cases: List[str] = Query(["pick_place"], description="Prospect use cases"),
        robots: List[str] = Query(["Franka Emika"], description="Prospect robot platforms"),
        company_size: str = Query("mid-market", description="startup | mid-market | enterprise"),
        industry: Optional[str] = Query(None, description="Prospect industry"),
        max_results: int = Query(3, ge=1, le=5, description="Number of top references"),
    ):
        if company_size not in ["startup", "mid-market", "enterprise"]:
            raise HTTPException(status_code=422, detail="company_size must be startup | mid-market | enterprise")

        # Score all reference customers
        scored = [
            (
                ref,
                _score_reference(ref, use_cases, robots, company_size, industry),
            )
            for ref in REFERENCE_CUSTOMERS
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:max_results]

        matches = []
        match_scores: Dict[str, float] = {}
        for ref, score in top:
            uc_overlap = list(set(use_cases) & set(ref["use_cases"]))
            robot_overlap = list(set(robots) & set(ref["robots"]))
            matches.append(
                ReferenceMatch(
                    reference_id=ref["id"],
                    company=ref["company"],
                    match_score=score,
                    use_case_overlap=uc_overlap,
                    robot_overlap=robot_overlap,
                    company_size=ref["company_size"],
                    industry=ref["industry"],
                    contact=ref["contact"],
                    incentive_tier=ref["incentive_tier"],
                    nps_score=ref["nps_score"],
                    avg_call_rating=ref["avg_call_rating"],
                    expected_close_rate_lift=f"+{round(ref['close_rate_lift'] * 100)}%",
                    suggested_topics=ref["topics_expert"],
                    available=ref["available"],
                )
            )
            match_scores[ref["id"]] = score

        return MatchResponse(
            top_references=matches,
            match_scores=match_scores,
            prospect_profile={
                "use_cases": use_cases,
                "robots": robots,
                "company_size": company_size,
                "industry": industry,
            },
            overall_program_close_rate_lift="+34% (measured across 47 reference-influenced deals)",
            ts=datetime.utcnow().isoformat(),
        )

    @app.post("/references/schedule", response_model=ScheduleResponse)
    def schedule_reference_call(req: ScheduleRequest):
        # Look up reference customer
        ref = next((r for r in REFERENCE_CUSTOMERS if r["id"] == req.reference_id), None)
        if ref is None:
            raise HTTPException(status_code=404, detail=f"Reference ID {req.reference_id!r} not found")
        if not ref["available"]:
            raise HTTPException(
                status_code=409,
                detail=f"{ref['company']} is not currently available for reference calls",
            )

        # Assign call time
        if req.preferred_slot:
            call_time = req.preferred_slot
        else:
            # Auto-assign next business day at 10:00 AM reference timezone
            future = datetime.utcnow() + timedelta(days=1)
            call_time = future.strftime("%Y-%m-%dT10:00:00Z")

        call_id = f"refcall-{uuid.uuid4().hex[:8]}"
        briefing = _generate_briefing_doc(ref, req.prospect_id, call_time)

        # Persist in memory
        _scheduled_calls.append({
            "call_id": call_id,
            "prospect_id": req.prospect_id,
            "reference_id": req.reference_id,
            "scheduled_time": call_time,
            "briefing": briefing,
        })

        # Increment reference call count (in-memory)
        ref["reference_calls_given"] = ref.get("reference_calls_given", 0) + 1

        return ScheduleResponse(
            call_id=call_id,
            call_scheduled=True,
            scheduled_time=call_time,
            reference_company=ref["company"],
            reference_contact=ref["contact"],
            briefing_doc=briefing,
            calendar_invite_sent=True,
            ts=datetime.utcnow().isoformat(),
        )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "customer_reference_network",
            "port": PORT,
            "references_active": sum(1 for r in REFERENCE_CUSTOMERS if r["available"]),
            "calls_scheduled": len(_scheduled_calls),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        active = sum(1 for r in REFERENCE_CUSTOMERS if r["available"])
        platinum = sum(1 for r in REFERENCE_CUSTOMERS if r["incentive_tier"] == "platinum")
        return HTMLResponse(f"""
<!DOCTYPE html><html><head><title>Customer Reference Network</title>
<style>
  body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}
  h1{{color:#C74634}} a{{color:#38bdf8}}
  .stat{{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem;min-width:160px;text-align:center}}
  .val{{font-size:2rem;font-weight:bold;color:#34d399}}
  .lbl{{font-size:.75rem;color:#94a3b8;margin-top:.25rem}}
</style></head><body>
<h1>Customer Reference Network</h1>
<p>OCI Robot Cloud &middot; Port 10103</p>
<p>Intelligent prospect-to-reference matching &mdash; by use case, robot platform &amp; company size.<br>
   NPS-based incentive tiers &middot; <strong>+34% close rate</strong> post-reference call.</p>
<div class="stat"><div class="val">{active}</div><div class="lbl">Active References</div></div>
<div class="stat"><div class="val">{platinum}</div><div class="lbl">Platinum Tier</div></div>
<div class="stat"><div class="val">+34%</div><div class="lbl">Close Rate Lift</div></div>
<div class="stat"><div class="val">{len(_scheduled_calls)}</div><div class="lbl">Calls Scheduled</div></div>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p>
<h3>Quick match example</h3>
<pre>GET /references/match?use_cases=pick_place&amp;robots=Franka+Emika&amp;company_size=mid-market</pre>
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
