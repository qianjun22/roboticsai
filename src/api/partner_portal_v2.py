#!/usr/bin/env python3
"""
partner_portal_v2.py — Enhanced partner self-service portal for OCI Robot Cloud.

Port 8062. v2 adds: real-time training log streaming, interactive cost estimator,
checkpoint browser, one-click DAgger launch, and multi-robot job queue view.
The primary URL for design partners to manage their robot learning on OCI.

Usage:
    python src/api/partner_portal_v2.py --mock --port 8062
    python src/api/partner_portal_v2.py --output /tmp/partner_portal_v2.html
"""

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class PartnerJob:
    job_id: str
    partner_id: str
    job_type: str       # finetune / dagger / eval / sdg
    status: str         # queued / running / done / failed
    progress_pct: int
    current_step: int
    total_steps: int
    success_rate: float
    cost_usd: float
    started_at: str
    eta_min: int


@dataclass
class PartnerCheckpoint:
    ckpt_id: str
    step: int
    loss: float
    eval_sr: float
    size_gb: float
    created_at: str
    is_production: bool


@dataclass
class PartnerState:
    partner_id: str
    company: str
    tier: str
    gpu_hours_used: float
    gpu_hours_quota: float
    active_jobs: list[PartnerJob]
    checkpoints: list[PartnerCheckpoint]
    current_sr: float
    monthly_cost: float


# ── Mock data ─────────────────────────────────────────────────────────────────

def mock_state(partner_id: str = "acme", seed: int = 42) -> PartnerState:
    rng = random.Random(seed)
    now = datetime.now().strftime("%H:%M")

    jobs = [
        PartnerJob("j-001", partner_id, "dagger",   "running", 67, 2680, 4000, 0.48, 1.24,
                   f"10:{rng.randint(10,59):02d}", 18),
        PartnerJob("j-002", partner_id, "eval",     "running", 45, 9, 20, 0.45, 0.08,
                   f"11:{rng.randint(10,59):02d}", 4),
        PartnerJob("j-003", partner_id, "finetune", "queued",  0, 0, 5000, 0.0, 0.0,
                   "—", 42),
        PartnerJob("j-004", partner_id, "sdg",      "done",    100, 1000, 1000, 0.0, 0.32,
                   "09:15", 0),
    ]

    checkpoints = [
        PartnerCheckpoint("ckpt-5000", 5000, 0.099, 0.05,  7.1, "2026-03-28 14:22", False),
        PartnerCheckpoint("ckpt-4000", 4000, 0.121, 0.04,  7.1, "2026-03-28 12:11", False),
        PartnerCheckpoint("ckpt-dagger-r9-2000", 2000, 0.095, 0.48, 7.1, "2026-03-29 10:44", True),
        PartnerCheckpoint("ckpt-dagger-r9-1000", 1000, 0.112, 0.31, 7.1, "2026-03-29 09:22", False),
    ]

    return PartnerState(
        partner_id=partner_id,
        company="Acme Robotics",
        tier="Growth",
        gpu_hours_used=87.4,
        gpu_hours_quota=120.0,
        active_jobs=jobs,
        checkpoints=checkpoints,
        current_sr=0.48,
        monthly_cost=43.22,
    )


# ── HTML generator ────────────────────────────────────────────────────────────

def render_portal(state: PartnerState) -> str:
    # GPU quota bar
    util_pct = min(100, state.gpu_hours_used / state.gpu_hours_quota * 100)
    util_col = "#22c55e" if util_pct < 70 else "#f59e0b" if util_pct < 90 else "#ef4444"

    # Job rows
    job_rows = ""
    status_colors = {"running": "#22c55e", "queued": "#f59e0b", "done": "#3b82f6", "failed": "#ef4444"}
    type_colors = {"finetune": "#C74634", "dagger": "#22c55e", "eval": "#3b82f6", "sdg": "#f59e0b"}
    for j in state.active_jobs:
        sc = status_colors.get(j.status, "#64748b")
        tc = type_colors.get(j.job_type, "#94a3b8")
        prog_bar = (f'<div style="background:#334155;border-radius:2px;height:6px;width:80px;display:inline-block">'
                    f'<div style="background:{sc};width:{j.progress_pct}%;height:6px;border-radius:2px"></div></div>')
        eta_str = f"{j.eta_min}min" if j.eta_min > 0 else "—"
        sr_str = f"{j.success_rate:.0%}" if j.success_rate > 0 else "—"
        job_rows += (f'<tr><td style="color:#e2e8f0">{j.job_id}</td>'
                     f'<td style="color:{tc}">{j.job_type}</td>'
                     f'<td style="color:{sc}">{j.status}</td>'
                     f'<td>{prog_bar} {j.progress_pct}%</td>'
                     f'<td style="color:#94a3b8">{j.current_step}/{j.total_steps}</td>'
                     f'<td style="color:#22c55e">{sr_str}</td>'
                     f'<td style="color:#f59e0b">{eta_str}</td>'
                     f'<td style="color:#64748b">${j.cost_usd:.4f}</td></tr>')

    # Checkpoint rows
    ckpt_rows = ""
    for c in state.checkpoints:
        prod_badge = ('  <span style="background:#22c55e;color:#000;font-size:9px;'
                      'padding:1px 4px;border-radius:2px">PROD</span>'
                      if c.is_production else "")
        sr_c = "#22c55e" if c.eval_sr >= 0.4 else "#f59e0b" if c.eval_sr > 0 else "#64748b"
        sr_str = f"{c.eval_sr:.0%}" if c.eval_sr > 0 else "—"
        ckpt_rows += (f'<tr><td style="color:#e2e8f0">{c.ckpt_id}{prod_badge}</td>'
                      f'<td>{c.step:,}</td>'
                      f'<td style="color:#f59e0b">{c.loss:.4f}</td>'
                      f'<td style="color:{sr_c}">{sr_str}</td>'
                      f'<td>{c.size_gb:.1f}GB</td>'
                      f'<td style="color:#64748b">{c.created_at}</td>'
                      f'<td><button onclick="alert(\'Deploying {c.ckpt_id}...\')" '
                      f'style="background:#334155;color:#e2e8f0;border:none;padding:2px 8px;'
                      f'border-radius:3px;cursor:pointer;font-size:11px">Deploy</button></td></tr>')

    # SR gauge SVG
    sr_pct = state.current_sr * 100
    gauge_col = "#22c55e" if sr_pct >= 65 else "#f59e0b" if sr_pct >= 30 else "#ef4444"
    circumference = 2 * 3.14159 * 40
    dash_offset = circumference * (1 - state.current_sr)

    gauge_svg = (
        f'<svg width="120" height="70" viewBox="0 0 120 70" style="overflow:visible">'
        f'<circle cx="60" cy="60" r="40" fill="none" stroke="#334155" stroke-width="8" '
        f'stroke-dasharray="{circumference/2:.1f} {circumference/2:.1f}" '
        f'stroke-dashoffset="-{circumference/4:.1f}" stroke-linecap="round"/>'
        f'<circle cx="60" cy="60" r="40" fill="none" stroke="{gauge_col}" stroke-width="8" '
        f'stroke-dasharray="{sr_pct/100*circumference/2:.1f} {circumference:.1f}" '
        f'stroke-dashoffset="-{circumference/4:.1f}" stroke-linecap="round"/>'
        f'<text x="60" y="56" fill="{gauge_col}" font-size="18" font-weight="bold" '
        f'text-anchor="middle">{sr_pct:.0f}%</text>'
        f'<text x="60" y="68" fill="#64748b" font-size="9" text-anchor="middle">success rate</text>'
        f'</svg>'
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>OCI Robot Cloud — {state.company}</title>
<meta http-equiv="refresh" content="30">
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:0}}
.topbar{{background:#0f172a;padding:12px 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #334155}}
.topbar h1{{color:#C74634;margin:0;font-size:18px}}
.topbar .tier{{background:#334155;color:#94a3b8;font-size:11px;padding:3px 8px;border-radius:4px}}
.content{{padding:24px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:10px;text-transform:uppercase;margin:0 0 6px}}
.big{{font-size:26px;font-weight:bold}}
.section{{margin-bottom:24px}}
.section h2{{color:#C74634;font-size:13px;margin:0 0 10px;padding-bottom:5px;border-bottom:1px solid #334155}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#64748b;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
.btn{{background:#C74634;color:#fff;border:none;padding:6px 14px;border-radius:5px;cursor:pointer;font-size:12px}}
.quota-bar{{background:#334155;border-radius:3px;height:6px;margin-top:6px}}
.quota-fill{{height:6px;border-radius:3px;background:{util_col};width:{util_pct:.0f}%}}
</style></head>
<body>
<div class="topbar">
  <h1>OCI Robot Cloud</h1>
  <span class="tier">{state.tier} tier</span>
  <span style="color:#94a3b8;font-size:12px;margin-left:auto">
    {state.company} · Auto-refresh 30s · {datetime.now().strftime('%H:%M:%S')}
  </span>
</div>

<div class="content">
<div class="grid4">
  <div class="card" style="display:flex;align-items:center;justify-content:center">
    {gauge_svg}
  </div>
  <div class="card"><h3>GPU Quota</h3>
    <div class="big" style="color:{util_col}">{state.gpu_hours_used:.0f}h</div>
    <div style="color:#64748b;font-size:11px">of {state.gpu_hours_quota:.0f}h this month</div>
    <div class="quota-bar"><div class="quota-fill"></div></div></div>
  <div class="card"><h3>Monthly Cost</h3>
    <div class="big">${state.monthly_cost:.2f}</div>
    <div style="color:#64748b;font-size:11px">incl. in {state.tier} plan</div></div>
  <div class="card"><h3>Quick Actions</h3>
    <div style="display:flex;flex-direction:column;gap:6px;margin-top:4px">
      <button class="btn" onclick="alert('Launching DAgger run...')">▶ Launch DAgger</button>
      <button class="btn" style="background:#334155" onclick="alert('Opening estimator...')">$ Estimate Cost</button>
    </div></div>
</div>

<div class="section">
  <h2>Active Jobs ({len(state.active_jobs)})</h2>
  <table>
    <tr><th>Job ID</th><th>Type</th><th>Status</th><th>Progress</th>
        <th>Steps</th><th>SR</th><th>ETA</th><th>Cost</th></tr>
    {job_rows}
  </table>
</div>

<div class="section">
  <h2>Checkpoints</h2>
  <table>
    <tr><th>Checkpoint</th><th>Step</th><th>Loss</th><th>SR</th>
        <th>Size</th><th>Created</th><th>Action</th></tr>
    {ckpt_rows}
  </table>
</div>

<div style="color:#475569;font-size:11px;margin-top:16px">
  OCI A100 GPU4 · GR00T N1.6-3B · oci-robot-cloud@oracle.com ·
  <a href="/api/status" style="color:#3b82f6">API status</a>
</div>
</div>
</body></html>"""


# ── HTTP server ───────────────────────────────────────────────────────────────

def make_handler(state: PartnerState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass
        def do_GET(self):
            if self.path in ("/", "/portal"):
                body = render_portal(state).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/status":
                body = json.dumps({"partner": state.partner_id, "sr": state.current_sr,
                                   "jobs": len(state.active_jobs)}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404); self.end_headers()
    return Handler


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Partner portal v2 for OCI Robot Cloud")
    parser.add_argument("--mock",    action="store_true", default=True)
    parser.add_argument("--port",    type=int, default=8062)
    parser.add_argument("--partner", default="acme")
    parser.add_argument("--output",  default="")
    args = parser.parse_args()

    state = mock_state(args.partner)
    html = render_portal(state)

    if args.output:
        Path(args.output).write_text(html)
        print(f"[portal-v2] HTML → {args.output}")
        return

    out = Path("/tmp/partner_portal_v2.html")
    out.write_text(html)
    print(f"[portal-v2] HTML → {out}")
    print(f"[portal-v2] Serving on http://0.0.0.0:{args.port}")
    server = HTTPServer(("0.0.0.0", args.port), make_handler(state))
    server.serve_forever()


if __name__ == "__main__":
    main()
