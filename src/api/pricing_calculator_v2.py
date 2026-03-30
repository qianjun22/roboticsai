#!/usr/bin/env python3
"""
pricing_calculator_v2.py — Advanced pricing calculator for OCI Robot Cloud.

v2 adds DAgger flywheel pricing, multi-embodiment bundles, annual commitment
discounts, and an interactive comparison against AWS/DGX/Lambda.
Runs as a standalone HTTP service on port 8060.

Usage:
    python src/api/pricing_calculator_v2.py --mock --port 8060
    python src/api/pricing_calculator_v2.py --output /tmp/pricing_v2.html
"""

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse


# ── Pricing tables ────────────────────────────────────────────────────────────

@dataclass
class PlatformRate:
    name: str
    gpu_hr_usd: float       # per GPU-hour
    finetune_step_usd: float
    inference_ms: float     # avg latency
    color: str


PLATFORMS = [
    PlatformRate("OCI A100",    4.20,  0.000043, 226, "#22c55e"),
    PlatformRate("OCI A10",     1.50,  0.000088, 310, "#3b82f6"),
    PlatformRate("AWS p4d",    23.85,  0.000413, 245, "#64748b"),
    PlatformRate("DGX Cloud",  36.71,  0.000635, 230, "#64748b"),
    PlatformRate("Lambda Labs", 5.09,  0.000088, 280, "#64748b"),
]

@dataclass
class ProductTier:
    name: str
    monthly_usd: float
    annual_usd: float           # annual commitment (15% off)
    gpu_hours: int              # included per month
    fine_tune_runs: int         # 5000-step runs per month
    dagger_iters: int           # DAgger iterations per month
    embodiments: int            # supported robot types
    support: str
    sla_uptime: float
    features: list[str]


TIERS = [
    ProductTier(
        "Pilot",
        500, 5100,
        gpu_hours=24, fine_tune_runs=10, dagger_iters=2, embodiments=1,
        support="email", sla_uptime=0.99,
        features=["GR00T N1.6 fine-tuning", "Genesis SDG (1k demos/mo)", "Basic eval harness",
                  "SDK access", "Community Slack"],
    ),
    ProductTier(
        "Growth",
        2000, 20400,
        gpu_hours=120, fine_tune_runs=50, dagger_iters=10, embodiments=2,
        support="Slack + priority email", sla_uptime=0.995,
        features=["Everything in Pilot", "DAgger flywheel automation", "Isaac Sim SDG",
                  "Multi-GPU fine-tuning (4× A100)", "Partner dashboard", "Weekly reports",
                  "Curriculum learning", "Custom domain randomization"],
    ),
    ProductTier(
        "Enterprise",
        8000, 81600,
        gpu_hours=500, fine_tune_runs=200, dagger_iters=50, embodiments=4,
        support="Dedicated CSM + 24/7 on-call", sla_uptime=0.999,
        features=["Everything in Growth", "Multi-embodiment bundle", "Federated training",
                  "Data privacy compliance cert", "Custom SLA", "Jetson edge deploy",
                  "NVIDIA partnership introductions", "GTC co-presentation opportunity",
                  "Gov cloud compliance (US-origin)", "Custom contract"],
    ),
]


# ── Cost computation ──────────────────────────────────────────────────────────

def compute_cost(demos: int, steps: int, dagger_iters: int,
                 platform: PlatformRate, use_lora: bool = True) -> dict:
    """Compute total training cost for a given configuration."""
    # Fine-tune cost
    it_per_sec = 2.35 if "A100" in platform.name else 1.05
    gpu_hrs = steps / (it_per_sec * 3600)
    finetune_cost = gpu_hrs * platform.gpu_hr_usd

    # DAgger cost: each iter = 50 episodes × 226ms + fine-tune
    if dagger_iters > 0:
        eval_hrs_per_iter = 50 * (platform.inference_ms / 1000) / 3600
        dagger_finetune_hrs = steps / (it_per_sec * 3600)
        dagger_cost = dagger_iters * (eval_hrs_per_iter + dagger_finetune_hrs) * platform.gpu_hr_usd
    else:
        dagger_cost = 0.0

    # LoRA discount: 2.2× speedup = 55% cost reduction
    lora_multiplier = 0.45 if use_lora else 1.0

    total = (finetune_cost + dagger_cost) * lora_multiplier
    return {
        "platform": platform.name,
        "finetune_cost": round(finetune_cost * lora_multiplier, 4),
        "dagger_cost": round(dagger_cost * lora_multiplier, 4),
        "total_cost": round(total, 4),
        "gpu_hrs": round(gpu_hrs * lora_multiplier, 3),
        "oci_savings_pct": None,   # filled in caller
    }


def compare_platforms(demos: int, steps: int, dagger_iters: int,
                      use_lora: bool = True) -> list[dict]:
    results = [compute_cost(demos, steps, dagger_iters, p, use_lora) for p in PLATFORMS]
    oci_cost = next(r["total_cost"] for r in results if "OCI A100" in r["platform"])
    for r in results:
        if r["platform"] != "OCI A100":
            r["oci_savings_pct"] = round((r["total_cost"] - oci_cost) / r["total_cost"] * 100, 1)
        else:
            r["oci_savings_pct"] = 0
    return results


# ── HTML generator ────────────────────────────────────────────────────────────

def render_html(demos: int = 1000, steps: int = 5000,
                dagger_iters: int = 9, use_lora: bool = True) -> str:
    comparison = compare_platforms(demos, steps, dagger_iters, use_lora)
    oci = next(r for r in comparison if "OCI A100" in r["platform"])
    aws = next(r for r in comparison if "AWS" in r["platform"])
    savings_vs_aws = round(aws["total_cost"] - oci["total_cost"], 2)
    savings_pct = round(savings_vs_aws / aws["total_cost"] * 100, 1)

    # Cost bars
    max_cost = max(r["total_cost"] for r in comparison)
    cost_bars = ""
    for r in comparison:
        bw = r["total_cost"] / max_cost * 380
        col = "#22c55e" if "OCI A100" in r["platform"] else \
              "#3b82f6" if "OCI A10" in r["platform"] else "#64748b"
        prefix = "★ " if col == "#22c55e" else ""
        savings_tag = (f'<span style="color:#94a3b8;font-size:10px"> '
                       f'({r["oci_savings_pct"]}% more expensive)</span>'
                       if r["oci_savings_pct"] else "")
        cost_bars += (
            f'<div style="margin-bottom:10px">'
            f'<div style="color:#94a3b8;font-size:11px;margin-bottom:2px">'
            f'{prefix}{r["platform"]}{savings_tag}</div>'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="background:{col};height:18px;width:{bw:.0f}px;border-radius:3px"></div>'
            f'<span style="color:{col};font-size:12px">${r["total_cost"]:.2f}</span>'
            f'</div></div>'
        )

    # Tier cards
    tier_cards = ""
    tier_colors = ["#64748b", "#3b82f6", "#22c55e"]
    for i, tier in enumerate(TIERS):
        col = tier_colors[i]
        features_html = "".join(
            f'<div style="color:#94a3b8;font-size:11px;padding:2px 0">✓ {f}</div>'
            for f in tier.features[:6]
        )
        savings_badge = ""
        if tier.annual_usd < tier.monthly_usd * 12:
            annual_savings = tier.monthly_usd * 12 - tier.annual_usd
            savings_badge = (f'<div style="color:#f59e0b;font-size:10px;margin-top:4px">'
                             f'Annual: ${tier.annual_usd:,}/yr (save ${annual_savings:,})</div>')
        tier_cards += f"""
          <div style="background:#0f172a;border-radius:8px;padding:16px;border-top:3px solid {col}">
            <div style="color:{col};font-size:16px;font-weight:bold;margin-bottom:4px">{tier.name}</div>
            <div style="font-size:28px;font-weight:bold;margin-bottom:2px">${tier.monthly_usd:,}<span style="font-size:14px;color:#64748b">/mo</span></div>
            {savings_badge}
            <div style="margin:10px 0;padding-top:10px;border-top:1px solid #334155">
              <div style="color:#94a3b8;font-size:11px">{tier.gpu_hours}h GPU/mo · {tier.fine_tune_runs} fine-tune runs · {tier.dagger_iters} DAgger iters</div>
              <div style="color:#94a3b8;font-size:11px">{tier.embodiments} robot type(s) · {tier.sla_uptime:.1%} SLA</div>
              <div style="color:#64748b;font-size:11px">{tier.support}</div>
            </div>
            {features_html}
          </div>"""

    # DAgger flywheel cost table
    dagger_rows = ""
    for n_iters in [2, 5, 9, 12]:
        costs = compare_platforms(demos, steps, n_iters, use_lora)
        oci_r = next(r for r in costs if "OCI A100" in r["platform"])
        aws_r = next(r for r in costs if "AWS" in r["platform"])
        dagger_rows += (f'<tr><td>{n_iters} iters</td>'
                        f'<td style="color:#22c55e">${oci_r["total_cost"]:.2f}</td>'
                        f'<td style="color:#64748b">${aws_r["total_cost"]:.2f}</td>'
                        f'<td style="color:#f59e0b">{aws_r["oci_savings_pct"]:.0f}%</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>OCI Robot Cloud — Pricing v2</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:32px;max-width:1000px}}
h1{{color:#C74634;margin:0 0 4px}}
h2{{color:#C74634;font-size:16px;margin:24px 0 12px;border-bottom:1px solid #334155;padding-bottom:6px}}
.tagline{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#64748b;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>OCI Robot Cloud — Pricing Calculator v2</h1>
<div class="tagline">Scenario: {demos} demos · {steps} fine-tune steps · {dagger_iters} DAgger iters · LoRA={'on' if use_lora else 'off'}</div>

<div class="grid2">
  <div>
    <h2>Platform Cost Comparison</h2>
    {cost_bars}
    <div style="color:#22c55e;font-size:13px;margin-top:8px">
      ★ OCI A100 saves ${savings_vs_aws:.2f} ({savings_pct:.0f}%) vs AWS p4d
    </div>
  </div>
  <div>
    <h2>DAgger Flywheel Cost (OCI vs AWS)</h2>
    <table>
      <tr><th>DAgger Iters</th><th>OCI A100</th><th>AWS p4d</th><th>OCI Savings</th></tr>
      {dagger_rows}
    </table>
    <div style="color:#94a3b8;font-size:11px;margin-top:8px">
      LoRA {'enabled (2.2× speedup)' if use_lora else 'disabled'}
    </div>
  </div>
</div>

<h2>Product Tiers</h2>
<div class="grid3">
  {tier_cards}
</div>

<div style="color:#64748b;font-size:11px;margin-top:16px;border-top:1px solid #334155;padding-top:12px">
  OCI A100 80GB GPU4 · NVIDIA GR00T N1.6-3B fine-tuning ·
  Generated {datetime.now().strftime('%Y-%m-%d')}
</div>
</body></html>"""


# ── HTTP server ───────────────────────────────────────────────────────────────

class PricingHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path in ("/", "/pricing"):
            demos = int(qs.get("demos", [1000])[0])
            steps = int(qs.get("steps", [5000])[0])
            dagger = int(qs.get("dagger", [9])[0])
            lora = qs.get("lora", ["true"])[0].lower() == "true"
            body = render_html(demos, steps, dagger, lora).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/compare":
            demos = int(qs.get("demos", [1000])[0])
            steps = int(qs.get("steps", [5000])[0])
            dagger = int(qs.get("dagger", [9])[0])
            data = compare_platforms(demos, steps, dagger)
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud pricing calculator v2")
    parser.add_argument("--mock",    action="store_true", default=True)
    parser.add_argument("--port",    type=int, default=8060)
    parser.add_argument("--output",  default="")
    parser.add_argument("--demos",   type=int, default=1000)
    parser.add_argument("--steps",   type=int, default=5000)
    parser.add_argument("--dagger",  type=int, default=9)
    parser.add_argument("--no-lora", action="store_true")
    args = parser.parse_args()

    html = render_html(args.demos, args.steps, args.dagger, not args.no_lora)

    if args.output:
        Path(args.output).write_text(html)
        print(f"[pricing-v2] HTML → {args.output}")
        json_out = Path(args.output).with_suffix(".json")
        data = compare_platforms(args.demos, args.steps, args.dagger, not args.no_lora)
        json_out.write_text(json.dumps(data, indent=2))
        print(f"[pricing-v2] JSON → {json_out}")
        return

    out = Path("/tmp/pricing_calculator_v2.html")
    out.write_text(html)
    print(f"[pricing-v2] HTML → {out}")

    print(f"[pricing-v2] Serving on http://0.0.0.0:{args.port}")
    server = HTTPServer(("0.0.0.0", args.port), PricingHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
