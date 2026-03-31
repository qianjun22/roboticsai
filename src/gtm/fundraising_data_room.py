"""
Series A VDR management — 7-section data room with completeness tracking and per-investor access control.
FastAPI service — OCI Robot Cloud
Port: 10089
"""
from __future__ import annotations
import json, random, time, uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field, EmailStr
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10089

# ---------------------------------------------------------------------------
# Data room structure — 7 canonical sections
# ---------------------------------------------------------------------------
DATA_ROOM_SECTIONS: Dict[str, dict] = {
    "legal": {
        "display_name": "Legal & Corporate",
        "documents": [
            {"id": "leg-001", "title": "Certificate of Incorporation",         "status": "complete",  "version": "v1.2", "updated": "2026-01-15"},
            {"id": "leg-002", "title": "Cap Table (Carta Export)",              "status": "complete",  "version": "v3.1", "updated": "2026-03-01"},
            {"id": "leg-003", "title": "IP Assignment Agreements",              "status": "complete",  "version": "v1.0", "updated": "2025-11-20"},
            {"id": "leg-004", "title": "Employee Option Pool Schedule",         "status": "complete",  "version": "v2.0", "updated": "2026-02-10"},
            {"id": "leg-005", "title": "Pending Litigation Summary",            "status": "missing",  "version": None,   "updated": None},
        ],
        "target_date": "2026-04-01",
    },
    "financial": {
        "display_name": "Financial",
        "documents": [
            {"id": "fin-001", "title": "Audited Financials FY2025",             "status": "complete",  "version": "v1.0", "updated": "2026-02-28"},
            {"id": "fin-002", "title": "3-Year Financial Model",                "status": "complete",  "version": "v4.2", "updated": "2026-03-20"},
            {"id": "fin-003", "title": "MRR / ARR Dashboard",                  "status": "complete",  "version": "v2.1", "updated": "2026-03-28"},
            {"id": "fin-004", "title": "Unit Economics (CAC / LTV)",            "status": "complete",  "version": "v1.3", "updated": "2026-03-15"},
            {"id": "fin-005", "title": "Q1 2026 Management Accounts",          "status": "in_progress", "version": None, "updated": None},
        ],
        "target_date": "2026-04-05",
    },
    "product": {
        "display_name": "Product",
        "documents": [
            {"id": "prd-001", "title": "Product Roadmap 2026-2027",             "status": "complete",  "version": "v2.0", "updated": "2026-03-10"},
            {"id": "prd-002", "title": "Demo Video — GR00T N1.6 + LIBERO",     "status": "complete",  "version": "v1.0", "updated": "2026-02-15"},
            {"id": "prd-003", "title": "Competitive Landscape Analysis",       "status": "complete",  "version": "v1.1", "updated": "2026-03-05"},
            {"id": "prd-004", "title": "NPS & User Research Summary",          "status": "in_progress", "version": None, "updated": None},
        ],
        "target_date": "2026-04-03",
    },
    "technical": {
        "display_name": "Technical",
        "documents": [
            {"id": "tec-001", "title": "System Architecture Diagram",           "status": "complete",  "version": "v3.0", "updated": "2026-03-18"},
            {"id": "tec-002", "title": "Security & Compliance Overview",        "status": "complete",  "version": "v1.2", "updated": "2026-02-20"},
            {"id": "tec-003", "title": "Benchmark Results (eval SR, latency)",  "status": "complete",  "version": "v2.3", "updated": "2026-03-25"},
            {"id": "tec-004", "title": "Scalability & Uptime SLA",             "status": "complete",  "version": "v1.0", "updated": "2026-03-01"},
            {"id": "tec-005", "title": "Penetration Test Report",              "status": "missing",  "version": None,   "updated": None},
        ],
        "target_date": "2026-04-08",
    },
    "customers": {
        "display_name": "Customers & Traction",
        "documents": [
            {"id": "cus-001", "title": "Design Partner Agreements (3 signed)",  "status": "complete",  "version": "v1.0", "updated": "2026-03-12"},
            {"id": "cus-002", "title": "Pilot Customer Case Studies",           "status": "complete",  "version": "v1.1", "updated": "2026-03-22"},
            {"id": "cus-003", "title": "LOI Pipeline Summary",                 "status": "complete",  "version": "v2.0", "updated": "2026-03-28"},
            {"id": "cus-004", "title": "Churn & Retention Analysis",           "status": "in_progress", "version": None, "updated": None},
        ],
        "target_date": "2026-04-02",
    },
    "team": {
        "display_name": "Team",
        "documents": [
            {"id": "tem-001", "title": "Org Chart & Bios",                      "status": "complete",  "version": "v1.0", "updated": "2026-01-30"},
            {"id": "tem-002", "title": "Key Employee Retention Agreements",     "status": "complete",  "version": "v1.0", "updated": "2025-12-15"},
            {"id": "tem-003", "title": "Hiring Plan 2026",                     "status": "complete",  "version": "v2.1", "updated": "2026-03-05"},
            {"id": "tem-004", "title": "Advisor Agreements",                   "status": "missing",  "version": None,   "updated": None},
        ],
        "target_date": "2026-04-01",
    },
    "ip": {
        "display_name": "Intellectual Property",
        "documents": [
            {"id": "ip-001",  "title": "Patent Applications (3 filed)",         "status": "complete",  "version": "v1.0", "updated": "2026-02-01"},
            {"id": "ip-002",  "title": "Trade Secret Register",                 "status": "complete",  "version": "v1.0", "updated": "2026-01-20"},
            {"id": "ip-003",  "title": "Open-Source License Audit",            "status": "complete",  "version": "v1.1", "updated": "2026-03-10"},
            {"id": "ip-004",  "title": "Freedom-to-Operate Opinion",           "status": "missing",  "version": None,   "updated": None},
        ],
        "target_date": "2026-04-10",
    },
}

# In-memory access log & granted access store
_access_grants: Dict[str, dict] = {}   # investor_id → grant record
_audit_log: List[dict] = []            # append-only audit trail


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _section_completeness(section_key: str) -> dict:
    sec = DATA_ROOM_SECTIONS[section_key]
    docs = sec["documents"]
    total = len(docs)
    complete = sum(1 for d in docs if d["status"] == "complete")
    in_progress = sum(1 for d in docs if d["status"] == "in_progress")
    missing_docs = [d["title"] for d in docs if d["status"] in ("missing", "in_progress")]
    pct = round(100 * complete / total) if total else 0
    return {
        "section":          section_key,
        "display_name":     sec["display_name"],
        "completeness_pct": pct,
        "documents_total":  total,
        "documents_complete": complete,
        "documents_in_progress": in_progress,
        "documents_missing": total - complete - in_progress,
        "gaps":             missing_docs,
        "target_date":      sec["target_date"],
        "documents":        docs,
    }


def _overall_completeness() -> float:
    all_docs = [
        d
        for sec in DATA_ROOM_SECTIONS.values()
        for d in sec["documents"]
    ]
    complete = sum(1 for d in all_docs if d["status"] == "complete")
    return round(100 * complete / len(all_docs)) if all_docs else 0


def _log_event(event_type: str, investor_id: str, detail: dict) -> dict:
    entry = {
        "event_id":    str(uuid.uuid4()),
        "event_type":  event_type,
        "investor_id": investor_id,
        "detail":      detail,
        "timestamp":   datetime.utcnow().isoformat() + "Z",
        "ip_address":  f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
    }
    _audit_log.append(entry)
    return entry


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
if USE_FASTAPI:
    app = FastAPI(
        title="Fundraising Data Room",
        version="1.0.0",
        description=(
            "Series A Virtual Data Room (VDR) management. "
            "7 sections: legal, financial, product, technical, customers, team, IP. "
            "Per-investor access control with watermarking and full audit trail."
        ),
    )

    # ---------- Request / Response models -----------------------------------

    class GrantAccessRequest(BaseModel):
        investor_id: str = Field(..., description="Unique investor identifier (e.g. 'sequoia-001')")
        investor_name: str = Field(..., description="Investor display name")
        investor_email: str = Field(..., description="Investor email address for access link delivery")
        sections: Optional[List[str]] = Field(
            None,
            description="Sections to grant access to. Omit for full data room access.",
        )
        expiry_days: int = Field(14, ge=1, le=90, description="Link expiry in days")
        nda_signed: bool = Field(False, description="Whether investor has signed NDA")

    # ---------- Endpoints ---------------------------------------------------

    @app.get("/fundraising/data_room")
    def get_data_room(section: Optional[str] = None):
        """Return data room completeness, documents, gaps, and target dates.

        - Pass `?section=<key>` to drill into a single section.
        - Omit to get a full summary across all 7 sections.
        """
        valid_sections = list(DATA_ROOM_SECTIONS.keys())

        if section:
            if section not in valid_sections:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown section '{section}'. Valid: {valid_sections}",
                )
            return _section_completeness(section)

        # Full summary
        sections_summary = [_section_completeness(k) for k in valid_sections]
        total_pct = _overall_completeness()
        critical_gaps = [
            {"section": s["display_name"], "gap": g}
            for s in sections_summary
            for g in s["gaps"]
        ]
        investor_count = len(_access_grants)
        return {
            "overall_completeness_pct": total_pct,
            "readiness": "investor_ready" if total_pct >= 90 else "in_preparation",
            "sections": sections_summary,
            "critical_gaps": critical_gaps,
            "total_gaps": len(critical_gaps),
            "active_investor_access_count": investor_count,
            "data_room_created": "2026-02-01T00:00:00Z",
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

    @app.post("/fundraising/grant_access")
    def grant_access(req: GrantAccessRequest):
        """Grant a specific investor access to the data room.

        Returns a unique access link (watermarked), a watermark ID for
        document-level traceability, and an audit log entry.
        """
        if not req.nda_signed:
            raise HTTPException(
                status_code=403,
                detail="NDA must be signed before data room access can be granted.",
            )

        sections_granted = req.sections if req.sections else list(DATA_ROOM_SECTIONS.keys())
        invalid = [s for s in sections_granted if s not in DATA_ROOM_SECTIONS]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid sections: {invalid}. Valid: {list(DATA_ROOM_SECTIONS.keys())}",
            )

        watermark_id = f"WM-{uuid.uuid4().hex[:12].upper()}"
        access_token = uuid.uuid4().hex
        expiry_dt = datetime.utcnow() + timedelta(days=req.expiry_days)
        access_link = (
            f"https://dataroom.oci-robot.cloud/vdr/{access_token}"
            f"?wm={watermark_id}&exp={expiry_dt.strftime('%Y%m%d')}"
        )

        grant_record = {
            "investor_id":    req.investor_id,
            "investor_name":  req.investor_name,
            "investor_email": req.investor_email,
            "access_token":   access_token,
            "watermark_id":   watermark_id,
            "access_link":    access_link,
            "sections":       sections_granted,
            "granted_at":     datetime.utcnow().isoformat() + "Z",
            "expires_at":     expiry_dt.isoformat() + "Z",
            "expiry_days":    req.expiry_days,
            "status":         "active",
            "views":          0,
            "last_viewed":    None,
        }
        _access_grants[req.investor_id] = grant_record

        audit_entry = _log_event(
            event_type="access_granted",
            investor_id=req.investor_id,
            detail={
                "investor_name": req.investor_name,
                "investor_email": req.investor_email,
                "sections": sections_granted,
                "watermark_id": watermark_id,
                "expires_at": expiry_dt.isoformat() + "Z",
            },
        )

        return {
            "access_link":    access_link,
            "watermark_id":   watermark_id,
            "investor_id":    req.investor_id,
            "sections_granted": sections_granted,
            "expires_at":     expiry_dt.isoformat() + "Z",
            "audit_log_entry": audit_entry,
            "instructions": (
                f"Send {access_link} to {req.investor_email}. "
                f"All downloaded documents will carry watermark {watermark_id}. "
                "Link expires in "
                f"{req.expiry_days} days."
            ),
        }

    @app.get("/fundraising/audit_log")
    def get_audit_log(investor_id: Optional[str] = None, limit: int = 50):
        """Return audit log, optionally filtered by investor."""
        log = _audit_log
        if investor_id:
            log = [e for e in log if e["investor_id"] == investor_id]
        return {
            "total_events": len(log),
            "events": log[-limit:],
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "fundraising_data_room",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        total_pct = _overall_completeness()
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Fundraising Data Room</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}
h1{{color:#C74634}}a{{color:#38bdf8}}.stat{{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}}</style></head><body>
<h1>Fundraising Data Room</h1><p>OCI Robot Cloud &middot; Port 10089</p>
<div class="stat">Series A VDR</div>
<div class="stat">7 Sections</div>
<div class="stat">Overall: {total_pct}% Complete</div>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/fundraising/data_room">Data Room</a></p>
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
