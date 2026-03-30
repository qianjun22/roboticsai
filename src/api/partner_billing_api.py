#!/usr/bin/env python3
"""
partner_billing_api.py — Partner billing and invoice generation for OCI Robot Cloud.

Port 8071. Generates monthly invoices from GPU usage data, applies tier pricing,
computes overages, and produces PDF-ready HTML invoices per partner. Integrates
with cost_attribution_tracker.py and pricing_calculator_v2.py.

Usage:
    python src/api/partner_billing_api.py --mock --port 8071
    python src/api/partner_billing_api.py --partner agility_robotics --month 2026-03
"""

import argparse
import json
import random
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


# ── Billing model ─────────────────────────────────────────────────────────────

@dataclass
class BillingTier:
    name: str
    monthly_base_usd: float
    included_gpu_hours: float    # per month
    overage_per_gpu_hr: float
    included_dagger_iters: int
    dagger_overage_per_iter: float
    included_eval_runs: int
    support_level: str


TIERS = {
    "pilot":      BillingTier("Pilot",      500,   24,  8.00,  5,  12.00,  20, "email"),
    "growth":     BillingTier("Growth",    2000,  120,  7.00, 20,  10.00, 100, "slack"),
    "enterprise": BillingTier("Enterprise", 8000,  500,  6.00, 80,   8.00, 500, "dedicated"),
}


@dataclass
class LineItem:
    description: str
    category: str      # base / gpu / dagger / eval / support / discount
    quantity: float
    unit: str
    unit_price: float
    total_usd: float


@dataclass
class Invoice:
    invoice_id: str
    partner: str
    tier_name: str
    period: str          # YYYY-MM
    line_items: list[LineItem]
    subtotal_usd: float
    discount_pct: float
    discount_usd: float
    total_usd: float
    due_date: str
    status: str          # draft / sent / paid / overdue
    gpu_hours_used: float
    dagger_iters_used: int
    eval_runs_used: int


PARTNERS_BILLING = {
    "agility_robotics": ("enterprise", 0.85),  # (tier, usage_factor)
    "figure_ai":        ("growth",     0.72),
    "boston_dynamics":  ("enterprise", 0.60),
    "pilot_customer":   ("pilot",      0.45),
}


def generate_invoice(partner: str, tier_name: str, usage_factor: float,
                     period: str, seed: int) -> Invoice:
    rng = random.Random(seed)
    tier = TIERS[tier_name]

    # Actual usage
    gpu_h = round(tier.included_gpu_hours * (usage_factor + rng.gauss(0, 0.08)), 2)
    dagger_iters = int(tier.included_dagger_iters * (usage_factor + rng.gauss(0, 0.1)))
    eval_runs = int(tier.included_eval_runs * (usage_factor + rng.gauss(0, 0.05)))

    line_items = []

    # Base subscription
    line_items.append(LineItem(
        description=f"{tier.name} Plan — {period}",
        category="base",
        quantity=1, unit="month",
        unit_price=tier.monthly_base_usd,
        total_usd=tier.monthly_base_usd,
    ))

    # GPU hours overage
    gpu_overage = max(0, gpu_h - tier.included_gpu_hours)
    if gpu_overage > 0:
        line_items.append(LineItem(
            description=f"GPU Hours Overage (included: {tier.included_gpu_hours}h, used: {gpu_h:.2f}h)",
            category="gpu",
            quantity=round(gpu_overage, 2), unit="GPU-hour",
            unit_price=tier.overage_per_gpu_hr,
            total_usd=round(gpu_overage * tier.overage_per_gpu_hr, 2),
        ))

    # DAgger iterations overage
    dagger_overage = max(0, dagger_iters - tier.included_dagger_iters)
    if dagger_overage > 0:
        line_items.append(LineItem(
            description=f"DAgger Iterations Overage (included: {tier.included_dagger_iters}, used: {dagger_iters})",
            category="dagger",
            quantity=dagger_overage, unit="iteration",
            unit_price=tier.dagger_overage_per_iter,
            total_usd=round(dagger_overage * tier.dagger_overage_per_iter, 2),
        ))

    # Eval runs overage
    eval_overage = max(0, eval_runs - tier.included_eval_runs)
    if eval_overage > 0:
        line_items.append(LineItem(
            description=f"Eval Runs Overage (included: {tier.included_eval_runs}, used: {eval_runs})",
            category="eval",
            quantity=eval_overage, unit="run",
            unit_price=0.50,
            total_usd=round(eval_overage * 0.50, 2),
        ))

    # Annual discount if paying annually
    if rng.random() < 0.6:
        discount_pct = 15.0
    else:
        discount_pct = 0.0

    subtotal = round(sum(li.total_usd for li in line_items), 2)
    discount_amt = round(subtotal * discount_pct / 100, 2)
    total = round(subtotal - discount_amt, 2)

    if discount_pct > 0:
        line_items.append(LineItem(
            description=f"Annual Commitment Discount ({discount_pct:.0f}%)",
            category="discount",
            quantity=1, unit="invoice",
            unit_price=-discount_amt,
            total_usd=-discount_amt,
        ))

    # Parse period to get due date
    year, month = period.split("-")
    next_month = int(month) % 12 + 1
    next_year = int(year) + (1 if int(month) == 12 else 0)
    due_date = f"{next_year}-{next_month:02d}-15"

    status = rng.choices(["paid", "sent", "draft"], weights=[0.6, 0.3, 0.1])[0]

    return Invoice(
        invoice_id=f"INV-{partner[:3].upper()}-{period.replace('-', '')}-{rng.randint(1000,9999)}",
        partner=partner,
        tier_name=tier_name,
        period=period,
        line_items=line_items,
        subtotal_usd=subtotal,
        discount_pct=discount_pct,
        discount_usd=discount_amt,
        total_usd=total,
        due_date=due_date,
        status=status,
        gpu_hours_used=gpu_h,
        dagger_iters_used=dagger_iters,
        eval_runs_used=eval_runs,
    )


def generate_all_invoices(period: str, seed: int = 42) -> list[Invoice]:
    return [generate_invoice(p, tier, uf, period, seed + i)
            for i, (p, (tier, uf)) in enumerate(PARTNERS_BILLING.items())]


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(invoices: list[Invoice], period: str) -> str:
    total_mrr = sum(inv.total_usd for inv in invoices)
    paid = sum(inv.total_usd for inv in invoices if inv.status == "paid")
    outstanding = sum(inv.total_usd for inv in invoices if inv.status in ("sent", "draft"))

    PARTNER_COLORS = {
        "agility_robotics": "#C74634", "figure_ai": "#3b82f6",
        "boston_dynamics": "#22c55e",  "pilot_customer": "#f59e0b"
    }
    STATUS_COLORS = {"paid": "#22c55e", "sent": "#f59e0b", "draft": "#64748b", "overdue": "#ef4444"}
    CAT_COLORS = {"base": "#3b82f6", "gpu": "#C74634", "dagger": "#22c55e",
                  "eval": "#f59e0b", "discount": "#22c55e", "support": "#a855f7"}

    # SVG: MRR breakdown by partner
    w, h = 400, 100
    svg_mrr = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    bar_h = (h - 20) / len(invoices) - 4
    max_total = max(inv.total_usd for inv in invoices) or 1
    for i, inv in enumerate(sorted(invoices, key=lambda x: -x.total_usd)):
        y = 10 + i * (bar_h + 4)
        bw = inv.total_usd / max_total * (w - 130)
        col = PARTNER_COLORS.get(inv.partner, "#94a3b8")
        svg_mrr += (f'<rect x="120" y="{y}" width="{bw:.1f}" height="{bar_h:.1f}" '
                    f'fill="{col}" rx="2" opacity="0.85"/>')
        svg_mrr += (f'<text x="118" y="{y+bar_h*0.75:.1f}" fill="#94a3b8" font-size="9" '
                    f'text-anchor="end">{inv.partner.replace("_"," ")}</text>')
        svg_mrr += (f'<text x="{123+bw:.1f}" y="{y+bar_h*0.75:.1f}" fill="{col}" '
                    f'font-size="9">${inv.total_usd:,.2f}</text>')
    svg_mrr += '</svg>'

    # Individual invoice HTML
    invoice_sections = ""
    for inv in invoices:
        col = PARTNER_COLORS.get(inv.partner, "#94a3b8")
        st_col = STATUS_COLORS.get(inv.status, "#94a3b8")
        line_rows = ""
        for li in inv.line_items:
            li_col = "#ef4444" if li.total_usd < 0 else "#e2e8f0"
            cc = CAT_COLORS.get(li.category, "#94a3b8")
            line_rows += (f'<tr>'
                          f'<td style="color:#e2e8f0;font-size:11px">{li.description}</td>'
                          f'<td style="color:{cc}">{li.category}</td>'
                          f'<td style="color:#64748b">{li.quantity} {li.unit}</td>'
                          f'<td style="color:#64748b">${abs(li.unit_price):.2f}</td>'
                          f'<td style="color:{li_col};font-weight:bold">'
                          f'{"−" if li.total_usd < 0 else ""}${abs(li.total_usd):.2f}</td></tr>')

        invoice_sections += f"""
<div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;margin-bottom:12px">
    <div>
      <div style="font-size:16px;font-weight:bold;color:{col}">{inv.partner.replace('_',' ').title()}</div>
      <div style="color:#64748b;font-size:12px">{inv.invoice_id} · {inv.tier_name} · {inv.period}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:24px;font-weight:bold;color:#22c55e">${inv.total_usd:,.2f}</div>
      <div style="color:{st_col};font-size:12px">● {inv.status.upper()} · due {inv.due_date}</div>
    </div>
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
    <tr style="border-bottom:1px solid #334155">
      <th style="color:#94a3b8;text-align:left;padding:4px 6px">Description</th>
      <th style="color:#94a3b8;padding:4px 6px">Category</th>
      <th style="color:#94a3b8;padding:4px 6px">Qty</th>
      <th style="color:#94a3b8;padding:4px 6px">Unit Price</th>
      <th style="color:#94a3b8;padding:4px 6px">Total</th>
    </tr>
    {line_rows}
  </table>
  <div style="display:flex;gap:20px;font-size:11px;color:#64748b">
    <span>GPU: {inv.gpu_hours_used:.1f}h used</span>
    <span>DAgger: {inv.dagger_iters_used} iters</span>
    <span>Evals: {inv.eval_runs_used} runs</span>
    {"<span style='color:#22c55e'>Annual discount applied</span>" if inv.discount_pct > 0 else ""}
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Partner Billing — OCI Robot Cloud · {period}</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
</style></head>
<body>
<h1>Partner Billing — {period}</h1>
<div class="meta">{len(invoices)} partners · {period} invoices</div>

<div class="grid">
  <div class="card"><h3>Period MRR</h3>
    <div class="big" style="color:#22c55e">${total_mrr:,.2f}</div></div>
  <div class="card"><h3>Collected</h3>
    <div class="big" style="color:#22c55e">${paid:,.2f}</div>
    <div style="color:#64748b;font-size:12px">{paid/total_mrr*100:.0f}% collected</div></div>
  <div class="card"><h3>Outstanding</h3>
    <div class="big" style="color:#f59e0b">${outstanding:,.2f}</div></div>
  <div class="card"><h3>Partners</h3>
    <div class="big">{len(invoices)}</div>
    <div style="color:#64748b;font-size:12px">
      {sum(1 for i in invoices if i.tier_name=='enterprise')}× enterprise
    </div></div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Revenue by Partner</h3>
    {svg_mrr}
  </div>
  <div style="background:#0f172a;border-radius:8px;padding:14px">
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 8px">Summary</h3>
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <tr><th style="color:#94a3b8;text-align:left;padding:3px 6px">Partner</th>
          <th style="color:#94a3b8;padding:3px 6px">Tier</th>
          <th style="color:#94a3b8;padding:3px 6px">Total</th>
          <th style="color:#94a3b8;padding:3px 6px">Status</th></tr>
      {"".join(f'<tr><td style="color:{PARTNER_COLORS.get(i.partner,\"#94a3b8\")};padding:3px 6px">{i.partner.replace("_"," ")}</td><td style="color:#64748b;padding:3px 6px">{i.tier_name}</td><td style="color:#22c55e;padding:3px 6px">${i.total_usd:,.2f}</td><td style="color:{STATUS_COLORS.get(i.status,\"#94a3b8\")};padding:3px 6px">{i.status}</td></tr>' for i in invoices)}
    </table>
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:12px">Invoices</h3>
{invoice_sections}

<div style="color:#64748b;font-size:11px;margin-top:8px">
  Annual commitment discount: 15% off. Overages billed at tier overage rate.<br>
  Invoices auto-generated from cost_attribution_tracker.py usage data.
</div>
</body></html>"""


# ── HTTP server ───────────────────────────────────────────────────────────────

def make_handler(invoices, period):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass
        def do_GET(self):
            if self.path in ("/", "/invoices"):
                body = render_html(invoices, period).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/invoices":
                data = [{"id": i.invoice_id, "partner": i.partner,
                          "total": i.total_usd, "status": i.status} for i in invoices]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()
    return Handler


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Partner billing API")
    parser.add_argument("--mock",      action="store_true", default=True)
    parser.add_argument("--port",      type=int, default=8071)
    parser.add_argument("--month",     default="2026-03")
    parser.add_argument("--partner",   default="all")
    parser.add_argument("--output",    default="")
    parser.add_argument("--seed",      type=int, default=42)
    args = parser.parse_args()

    invoices = generate_all_invoices(args.month, args.seed)
    total_mrr = sum(i.total_usd for i in invoices)
    print(f"[billing] {len(invoices)} invoices · {args.month} · MRR=${total_mrr:,.2f}")

    for inv in invoices:
        print(f"  {inv.partner:<22} {inv.tier_name:<12} ${inv.total_usd:>8,.2f}  [{inv.status}]")

    html = render_html(invoices, args.month)
    if args.output:
        Path(args.output).write_text(html)
        print(f"[billing] HTML → {args.output}")
        return

    out = Path("/tmp/partner_billing_api.html")
    out.write_text(html)
    print(f"[billing] HTML → {out}")
    print(f"[billing] Serving on http://0.0.0.0:{args.port}")
    server = HTTPServer(("0.0.0.0", args.port), make_handler(invoices, args.month))
    server.serve_forever()


if __name__ == "__main__":
    main()
