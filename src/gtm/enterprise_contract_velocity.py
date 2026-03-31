"""
Contract cycle time reduction — 23 days→15 days target via stage analysis and automated redline suggestions.
FastAPI service — OCI Robot Cloud
Port: 10105
"""
from __future__ import annotations
import json, math, random, time, re
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10105

# --- Domain constants ---

# Stage definitions: (stage_name, baseline_days, target_days, typical_bottleneck)
CONTRACT_STAGES = {
    "NDA": {
        "baseline_days": 3,
        "target_days": 1,
        "bottleneck": "mutual vs. one-way NDA negotiation",
        "acceleration_tactics": [
            "Use pre-approved standard mutual NDA template",
            "DocuSign e-signature same day",
            "Auto-approve for companies <$50M ARR with clean legal history",
        ],
    },
    "MSA": {
        "baseline_days": 8,
        "target_days": 5,
        "bottleneck": "liability caps and indemnification redlines",
        "acceleration_tactics": [
            "Pre-negotiate Oracle standard liability cap (2x fees)",
            "Automated redline on indemnification deviations",
            "Legal pre-approval for Fortune 500 counterparties",
            "Parallel DPA + MSA review when possible",
        ],
    },
    "DPA": {
        "baseline_days": 8,
        "target_days": 5,
        "bottleneck": "GDPR Article 28 processor requirements and SCCs",
        "acceleration_tactics": [
            "DPA pre-approval: accept Oracle standard DPA with no redlines",
            "Pre-executed SCCs for EU data transfers",
            "Auto-classify data types from contract text",
            "Infosec questionnaire automation (shared assessments)",
        ],
    },
    "SoW": {
        "baseline_days": 4,
        "target_days": 4,
        "bottleneck": "scope definition and milestone payment schedule",
        "acceleration_tactics": [
            "Use modular SoW templates per use case (fine-tuning, inference, SDG)",
            "Pre-approved pricing tiers in CPQ",
            "Auto-generate milestone schedule from project duration",
        ],
    },
}

BASELINE_TOTAL_DAYS = sum(s["baseline_days"] for s in CONTRACT_STAGES.values())  # 23
TARGET_TOTAL_DAYS = sum(s["target_days"] for s in CONTRACT_STAGES.values())       # 15

# Standard terms we check for in contract text
STANDARD_TERMS_CHECKS = {
    "liability_cap": {
        "pattern": r"liabilit\w+.{0,60}(cap|limit|exceed)",
        "standard": "Aggregate liability capped at 2× fees paid in prior 12 months",
        "risk": "high",
    },
    "ip_ownership": {
        "pattern": r"intellectual property|IP ownership|work.for.hire",
        "standard": "Customer owns customer data; Oracle owns platform and models",
        "risk": "critical",
    },
    "data_processing": {
        "pattern": r"personal data|GDPR|data processor|sub.?processor",
        "standard": "Oracle standard DPA applies; SCCs executed for EU transfers",
        "risk": "high",
    },
    "termination": {
        "pattern": r"terminat\w+.{0,40}(convenience|notice|days)",
        "standard": "Either party may terminate for convenience with 30-day notice",
        "risk": "medium",
    },
    "governing_law": {
        "pattern": r"governing law|jurisdiction|venue",
        "standard": "Governed by laws of State of California; Santa Clara County venue",
        "risk": "medium",
    },
    "confidentiality": {
        "pattern": r"confidential\w*|proprietary information",
        "standard": "3-year confidentiality period post-disclosure",
        "risk": "low",
    },
    "sla": {
        "pattern": r"service level|SLA|uptime|availability",
        "standard": "99.5% monthly uptime SLA; 3-tier credit schedule",
        "risk": "medium",
    },
}

# Redline suggestion templates
REDLINE_TEMPLATES = {
    "liability_cap_too_low": "Customer requests uncapped liability — suggest: 2× fees in prior 12 months (Oracle standard). Escalate if >$10M ARR deal.",
    "ip_ownership_conflict": "Clause grants customer rights to Oracle model weights — non-starter. Redline: customer retains rights to fine-tuned artifacts only; Oracle retains base model IP.",
    "perpetual_data_retention": "Contract specifies perpetual data retention — suggest: 90-day post-termination retention with secure deletion certificate.",
    "uncapped_indemnification": "Indemnification clause has no cap — suggest: mutual indemnification capped at contract value for IP infringement claims only.",
    "source_code_escrow": "Source code escrow requested — standard response: OCI offers binary escrow via Iron Mountain; full source not available.",
}


def _analyze_stage(contract_type: str, stage: str) -> Dict[str, Any]:
    s = CONTRACT_STAGES.get(stage, CONTRACT_STAGES["MSA"])
    # Slight variance by contract type
    multiplier = {"enterprise": 1.0, "mid_market": 0.85, "startup": 0.65}.get(contract_type, 1.0)
    actual_days = round(s["baseline_days"] * multiplier, 1)
    projected_days = round(s["target_days"] * multiplier, 1)
    return {
        "stage": stage,
        "baseline_days": actual_days,
        "target_days": projected_days,
        "days_saved": round(actual_days - projected_days, 1),
        "bottleneck": s["bottleneck"],
        "acceleration_tactics": s["acceleration_tactics"],
    }


def _check_standard_terms(text: str) -> Dict[str, Any]:
    """Scan contract text for standard terms deviations."""
    results = {}
    text_lower = text.lower()
    for term_name, spec in STANDARD_TERMS_CHECKS.items():
        match = re.search(spec["pattern"], text_lower)
        results[term_name] = {
            "found_in_contract": bool(match),
            "standard_term": spec["standard"],
            "risk_level": spec["risk"],
            "matched_text": text[match.start():match.start()+80].strip() if match else None,
        }
    return results


def _generate_redline_suggestions(text: str) -> List[Dict[str, str]]:
    """Generate redline suggestions based on contract text patterns."""
    suggestions = []
    text_lower = text.lower()

    if re.search(r"unlimited|uncapped|no limit.{0,20}liabilit", text_lower):
        suggestions.append({"issue": "uncapped_liability", "severity": "critical", "suggestion": REDLINE_TEMPLATES["liability_cap_too_low"]})

    if re.search(r"model weight|training data|algorithm.{0,30}own|assign.{0,30}model", text_lower):
        suggestions.append({"issue": "ip_ownership_conflict", "severity": "critical", "suggestion": REDLINE_TEMPLATES["ip_ownership_conflict"]})

    if re.search(r"perpetual|indefinite.{0,20}retain|never delet", text_lower):
        suggestions.append({"issue": "perpetual_data_retention", "severity": "high", "suggestion": REDLINE_TEMPLATES["perpetual_data_retention"]})

    if re.search(r"indemnif\w+.{0,30}(unlimited|no cap|any amount)", text_lower):
        suggestions.append({"issue": "uncapped_indemnification", "severity": "high", "suggestion": REDLINE_TEMPLATES["uncapped_indemnification"]})

    if re.search(r"source code escrow|software escrow", text_lower):
        suggestions.append({"issue": "source_code_escrow", "severity": "medium", "suggestion": REDLINE_TEMPLATES["source_code_escrow"]})

    return suggestions


def _should_escalate(text: str, redlines: List[Dict]) -> bool:
    critical_redlines = [r for r in redlines if r.get("severity") == "critical"]
    return len(critical_redlines) > 0 or re.search(r"\$[5-9][0-9]M|\$[1-9][0-9]{2}M|billion", text) is not None


if USE_FASTAPI:
    app = FastAPI(title="Enterprise Contract Velocity", version="1.0.0")

    class ContractVelocityRequest(BaseModel):
        contract_type: str = "enterprise"  # enterprise | mid_market | startup

    class ContractReviewRequest(BaseModel):
        contract_text: str
        contract_type: Optional[str] = "enterprise"

    @app.get("/legal/contract_velocity")
    def contract_velocity(contract_type: str = "enterprise"):
        stage_analyses = [_analyze_stage(contract_type, stage) for stage in CONTRACT_STAGES]

        multiplier = {"enterprise": 1.0, "mid_market": 0.85, "startup": 0.65}.get(contract_type, 1.0)
        total_baseline = round(BASELINE_TOTAL_DAYS * multiplier, 1)
        total_target = round(TARGET_TOTAL_DAYS * multiplier, 1)
        total_saved = round(total_baseline - total_target, 1)
        improvement_pct = round((total_saved / total_baseline) * 100, 1)

        # Identify primary bottleneck (stage with most days saved)
        bottleneck_stage = max(stage_analyses, key=lambda s: s["days_saved"])

        return {
            "contract_type": contract_type,
            "avg_days_baseline": total_baseline,
            "avg_days_target": total_target,
            "days_saved": total_saved,
            "projected_improvement_pct": f"{improvement_pct}%",
            "bottleneck": {
                "stage": bottleneck_stage["stage"],
                "issue": bottleneck_stage["bottleneck"],
                "days_at_risk": bottleneck_stage["baseline_days"],
            },
            "stage_breakdown": stage_analyses,
            "acceleration_tactics": [
                tactic
                for s in stage_analyses
                for tactic in s["acceleration_tactics"]
            ],
            "dpa_pre_approval_eligible": contract_type in ("enterprise", "mid_market"),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.post("/legal/contract_review")
    def contract_review(req: ContractReviewRequest):
        if not req.contract_text or len(req.contract_text) < 20:
            raise HTTPException(status_code=400, detail="contract_text too short")

        standard_terms = _check_standard_terms(req.contract_text)
        redline_suggestions = _generate_redline_suggestions(req.contract_text)
        escalate = _should_escalate(req.contract_text, redline_suggestions)

        critical_count = sum(1 for r in redline_suggestions if r["severity"] == "critical")
        high_count = sum(1 for r in redline_suggestions if r["severity"] == "high")
        medium_count = sum(1 for r in redline_suggestions if r["severity"] == "medium")

        return {
            "standard_terms_check": standard_terms,
            "redline_suggestions": redline_suggestions,
            "redline_summary": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "total": len(redline_suggestions),
            },
            "escalation_flag": escalate,
            "escalation_reason": "Critical IP or liability issues detected — requires Legal VP review" if escalate else None,
            "estimated_review_time_hours": 2 + critical_count * 4 + high_count * 2,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "enterprise_contract_velocity", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Enterprise Contract Velocity</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>Enterprise Contract Velocity</h1><p>OCI Robot Cloud · Port 10105</p>
<p>Contract cycle time reduction: 23 days → 15 days target · Stage analysis · Automated redlines</p>
<div class="stat">NDA: 3d → 1d</div>
<div class="stat">MSA: 8d → 5d</div>
<div class="stat">DPA: 8d → 5d</div>
<div class="stat">SoW: 4d → 4d</div>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/legal/contract_velocity">Velocity Stats</a></p>
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
