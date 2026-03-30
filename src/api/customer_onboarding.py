"""
customer_onboarding.py — OCI Robot Cloud design partner onboarding pipeline.

Manages design partner onboarding from signup → pilot → production; tracks
setup checklist, API keys, and first fine-tune run. Serves a dark-themed
Kanban dashboard at port 8059.
"""

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class OnboardingStage(Enum):
    SIGNUP = "Signup"
    API_KEY_ISSUED = "API Key Issued"
    ENVIRONMENT_SETUP = "Environment Setup"
    FIRST_FINETUNE = "First Fine-Tune"
    EVAL_COMPLETE = "Eval Complete"
    PRODUCTION = "Production"


STAGE_ORDER = list(OnboardingStage)

ONBOARDING_CHECKLIST_STEPS = [
    "oci_account_linked",
    "api_key_issued",
    "sdk_installed",
    "first_dataset_uploaded",
    "first_finetune_run",
    "first_eval_run",
    "webhook_configured",
    "production_approved",
]

# Steps that should be complete at each stage boundary
STAGE_CHECKLIST_MAP: Dict[OnboardingStage, List[str]] = {
    OnboardingStage.SIGNUP: [],
    OnboardingStage.API_KEY_ISSUED: ["oci_account_linked", "api_key_issued"],
    OnboardingStage.ENVIRONMENT_SETUP: ["oci_account_linked", "api_key_issued", "sdk_installed"],
    OnboardingStage.FIRST_FINETUNE: [
        "oci_account_linked", "api_key_issued", "sdk_installed",
        "first_dataset_uploaded", "first_finetune_run",
    ],
    OnboardingStage.EVAL_COMPLETE: [
        "oci_account_linked", "api_key_issued", "sdk_installed",
        "first_dataset_uploaded", "first_finetune_run", "first_eval_run",
        "webhook_configured",
    ],
    OnboardingStage.PRODUCTION: ONBOARDING_CHECKLIST_STEPS,
}


@dataclass
class Customer:
    customer_id: str
    company: str
    contact_email: str
    tier: str  # Pilot | Growth | Enterprise
    stage: OnboardingStage
    created_at: datetime
    notes: str = ""
    checklist: Dict[str, bool] = field(default_factory=dict)

    def days_in_current_stage(self) -> int:
        """Approximate days in current stage (mock: based on created_at offset)."""
        delta = datetime.utcnow() - self.created_at
        stage_idx = STAGE_ORDER.index(self.stage)
        # Distribute total days evenly across stages reached
        if stage_idx == 0:
            return delta.days
        per_stage = max(1, delta.days // (stage_idx + 1))
        return per_stage

    def checklist_pct(self) -> int:
        if not self.checklist:
            return 0
        done = sum(1 for v in self.checklist.values() if v)
        return int(done / len(self.checklist) * 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "company": self.company,
            "contact_email": self.contact_email,
            "tier": self.tier,
            "stage": self.stage.name,
            "stage_label": self.stage.value,
            "created_at": self.created_at.isoformat(),
            "notes": self.notes,
            "checklist": self.checklist,
            "checklist_pct": self.checklist_pct(),
            "days_in_stage": self.days_in_current_stage(),
        }


def _build_checklist(stage: OnboardingStage) -> Dict[str, bool]:
    completed = set(STAGE_CHECKLIST_MAP.get(stage, []))
    return {step: (step in completed) for step in ONBOARDING_CHECKLIST_STEPS}


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

def _mock_customers() -> Dict[str, Customer]:
    customers = [
        Customer(
            customer_id="cust-001",
            company="Acme Robotics",
            contact_email="eng@acmerobotics.ai",
            tier="Enterprise",
            stage=OnboardingStage.EVAL_COMPLETE,
            created_at=datetime.utcnow() - timedelta(days=21),
            notes="Ready for production approval; waiting on legal sign-off.",
            checklist=_build_checklist(OnboardingStage.EVAL_COMPLETE),
        ),
        Customer(
            customer_id="cust-002",
            company="BotCo",
            contact_email="dev@botco.io",
            tier="Growth",
            stage=OnboardingStage.FIRST_FINETUNE,
            created_at=datetime.utcnow() - timedelta(days=10),
            notes="Running first fine-tune on pick-and-place task.",
            checklist=_build_checklist(OnboardingStage.FIRST_FINETUNE),
        ),
        Customer(
            customer_id="cust-003",
            company="NexaArm",
            contact_email="infra@nexaarm.com",
            tier="Pilot",
            stage=OnboardingStage.API_KEY_ISSUED,
            created_at=datetime.utcnow() - timedelta(days=3),
            notes="SDK install in progress; blocked on VPN setup.",
            checklist=_build_checklist(OnboardingStage.API_KEY_ISSUED),
        ),
    ]
    return {c.customer_id: c for c in customers}


CUSTOMERS: Dict[str, Customer] = _mock_customers()


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def advance_stage(customer: Customer) -> Optional[OnboardingStage]:
    idx = STAGE_ORDER.index(customer.stage)
    if idx + 1 >= len(STAGE_ORDER):
        return None
    next_stage = STAGE_ORDER[idx + 1]
    customer.stage = next_stage
    # Fill checklist for newly reached stage
    for step in STAGE_CHECKLIST_MAP.get(next_stage, []):
        customer.checklist[step] = True
    return next_stage


def onboarding_summary() -> Dict[str, Any]:
    stage_counts: Dict[str, int] = {s.name: 0 for s in OnboardingStage}
    total_days = 0
    prod_count = 0
    for c in CUSTOMERS.values():
        stage_counts[c.stage.name] += 1
        if c.stage == OnboardingStage.PRODUCTION:
            total_days += (datetime.utcnow() - c.created_at).days
            prod_count += 1
    avg_days = round(total_days / prod_count, 1) if prod_count else None
    return {
        "total_customers": len(CUSTOMERS),
        "stage_funnel": stage_counts,
        "avg_days_to_production": avg_days,
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def render_html(customers: Dict[str, Customer]) -> str:
    stage_groups: Dict[OnboardingStage, List[Customer]] = {s: [] for s in OnboardingStage}
    for c in customers.values():
        stage_groups[c.stage].append(c)

    TIER_COLORS = {"Pilot": "#6366f1", "Growth": "#10b981", "Enterprise": "#f59e0b"}
    STAGE_COLORS = {
        OnboardingStage.SIGNUP: "#374151",
        OnboardingStage.API_KEY_ISSUED: "#1d4ed8",
        OnboardingStage.ENVIRONMENT_SETUP: "#7c3aed",
        OnboardingStage.FIRST_FINETUNE: "#b45309",
        OnboardingStage.EVAL_COMPLETE: "#0f766e",
        OnboardingStage.PRODUCTION: "#15803d",
    }

    def checklist_html(cl: Dict[str, bool]) -> str:
        rows = ""
        for step, done in cl.items():
            icon = "&#10003;" if done else "&#9675;"
            color = "#10b981" if done else "#6b7280"
            label = step.replace("_", " ").title()
            rows += f'<div style="color:{color};font-size:11px;margin:2px 0">{icon} {label}</div>'
        return rows

    columns = ""
    for stage in OnboardingStage:
        cards = ""
        for c in stage_groups[stage]:
            tier_color = TIER_COLORS.get(c.tier, "#9ca3af")
            pct = c.checklist_pct()
            days = c.days_in_current_stage()
            cards += f"""
            <div style="background:#1f2937;border-radius:8px;padding:12px;margin-bottom:10px;
                        border-left:3px solid {tier_color}">
              <div style="font-weight:600;font-size:13px;color:#f9fafb">{c.company}</div>
              <div style="font-size:11px;color:#9ca3af;margin:2px 0">{c.contact_email}</div>
              <div style="display:flex;gap:6px;align-items:center;margin:6px 0">
                <span style="background:{tier_color};color:#000;border-radius:3px;
                             padding:1px 6px;font-size:10px;font-weight:700">{c.tier}</span>
                <span style="color:#6b7280;font-size:10px">{days}d in stage</span>
              </div>
              <div style="background:#374151;border-radius:4px;height:4px;margin:6px 0">
                <div style="background:#10b981;width:{pct}%;height:4px;border-radius:4px"></div>
              </div>
              <div style="font-size:10px;color:#6b7280;margin-bottom:6px">{pct}% checklist</div>
              {checklist_html(c.checklist)}
              {"" if not c.notes else f'<div style="font-size:10px;color:#fbbf24;margin-top:6px;font-style:italic">{c.notes}</div>'}
            </div>"""

        hdr_color = STAGE_COLORS[stage]
        count = len(stage_groups[stage])
        columns += f"""
        <div style="min-width:200px;max-width:220px;flex-shrink:0">
          <div style="background:{hdr_color};border-radius:6px 6px 0 0;padding:8px 12px;
                      font-size:12px;font-weight:700;color:#fff;display:flex;
                      justify-content:space-between;align-items:center">
            <span>{stage.value}</span>
            <span style="background:rgba(255,255,255,0.25);border-radius:10px;
                         padding:1px 8px">{count}</span>
          </div>
          <div style="background:#111827;border-radius:0 0 6px 6px;padding:10px;
                      min-height:120px">{cards or '<div style="color:#4b5563;font-size:11px;text-align:center;padding:20px 0">No partners</div>'}</div>
        </div>"""

    summary = onboarding_summary()
    funnel_items = " &rarr; ".join(
        f"<b>{v}</b> {OnboardingStage[k].value}"
        for k, v in summary["stage_funnel"].items()
        if v > 0
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Robot Cloud — Customer Onboarding</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont,
            "Segoe UI", sans-serif; padding: 24px; }}
    h1 {{ font-size: 20px; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }}
    .subtitle {{ font-size: 13px; color: #64748b; margin-bottom: 20px; }}
    .stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
    .stat {{ background: #1e293b; border-radius: 8px; padding: 12px 20px; }}
    .stat-val {{ font-size: 22px; font-weight: 700; color: #38bdf8; }}
    .stat-lbl {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
    .funnel {{ background: #1e293b; border-radius: 8px; padding: 12px 20px;
               font-size: 12px; color: #94a3b8; margin-bottom: 24px; }}
    .kanban {{ display: flex; gap: 14px; overflow-x: auto; padding-bottom: 12px; }}
    .cta {{ margin-top: 24px; }}
    .cta button {{ background: #2563eb; color: #fff; border: none; border-radius: 6px;
                   padding: 10px 22px; font-size: 13px; font-weight: 600; cursor: pointer; }}
    .cta button:hover {{ background: #1d4ed8; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Design Partner Onboarding</h1>
  <div class="subtitle">Signup &rarr; Pilot &rarr; Production pipeline &bull; port 8059</div>

  <div class="stats">
    <div class="stat">
      <div class="stat-val">{summary["total_customers"]}</div>
      <div class="stat-lbl">Total Partners</div>
    </div>
    <div class="stat">
      <div class="stat-val">{summary["stage_funnel"].get("PRODUCTION", 0)}</div>
      <div class="stat-lbl">In Production</div>
    </div>
    <div class="stat">
      <div class="stat-val">{summary["avg_days_to_production"] or "N/A"}</div>
      <div class="stat-lbl">Avg Days to Production</div>
    </div>
  </div>

  <div class="funnel">Funnel: {funnel_items}</div>

  <div class="kanban">{columns}</div>

  <div class="cta">
    <button onclick="alert('Partner onboarding form — integrate with CRM')">
      + Onboard New Partner
    </button>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class OnboardingHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access logs
        pass

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        if path == "" or path == "/":
            self._send_html(render_html(CUSTOMERS))
        elif path == "/customers":
            self._send_json([c.to_dict() for c in CUSTOMERS.values()])
        elif len(parts) == 2 and parts[0] == "customers":
            cid = parts[1]
            if cid in CUSTOMERS:
                self._send_json(CUSTOMERS[cid].to_dict())
            else:
                self._send_json({"error": "not found"}, 404)
        elif path == "/onboarding/summary":
            self._send_json(onboarding_summary())
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        # POST /customers/{id}/advance
        if len(parts) == 3 and parts[0] == "customers" and parts[2] == "advance":
            cid = parts[1]
            if cid not in CUSTOMERS:
                self._send_json({"error": "not found"}, 404)
                return
            new_stage = advance_stage(CUSTOMERS[cid])
            if new_stage is None:
                self._send_json({"error": "already in production"}, 400)
            else:
                self._send_json({
                    "customer_id": cid,
                    "new_stage": new_stage.name,
                    "new_stage_label": new_stage.value,
                    "customer": CUSTOMERS[cid].to_dict(),
                })
        else:
            self._send_json({"error": "not found"}, 404)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud customer onboarding service")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use mock customer data (default: True)")
    parser.add_argument("--port", type=int, default=8059, help="HTTP port (default: 8059)")
    parser.add_argument("--output", default="/tmp/customer_onboarding.html",
                        help="Path to write static HTML snapshot")
    args = parser.parse_args()

    html = render_html(CUSTOMERS)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as fh:
        fh.write(html)
    print(f"[onboarding] HTML snapshot written to {args.output}")

    server = HTTPServer(("0.0.0.0", args.port), OnboardingHandler)
    print(f"[onboarding] Serving on http://0.0.0.0:{args.port}  (Ctrl-C to stop)")
    print(f"[onboarding] Routes: GET /  GET /customers  GET /customers/{{id}}")
    print(f"[onboarding]         POST /customers/{{id}}/advance  GET /onboarding/summary")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[onboarding] Shutting down.")


if __name__ == "__main__":
    main()
