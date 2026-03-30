"""oci_billing_dashboard.py
Tracks OCI compute billing for Robot Cloud operations \u2014 March 2026.
Monthly / weekly breakdown with HTML dashboard. stdlib + numpy only."""
from __future__ import annotations
import math, random, uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Tuple

GPU_RATES: Dict[str,float]={"A100_80GB":4.10,"A100_40GB":2.80,"A100_80GB_spot":1.85}
MONTHLY_BUDGET_USD=500.0
ALERT_THRESHOLD_PCT=85.0
JOB_TYPES=["fine_tune","dagger_collect","closed_loop_eval","sdg","inference","misc"]
PARTNERS=["internal","acme_robotics","blue_sky_labs","nexgen_auto","partner_demo"]

@dataclass
class BillingRecord:
    record_id:str; date:date; job_type:str; gpu_type:str
    hours:float; cost_usd:float; partner_id:str; tags:List[str]=field(default_factory=list)

@dataclass
class MonthlyBudget:
    month:str; budget_usd:float; spend_usd:float; forecast_usd:float; alert_threshold_pct:float

def generate_billing_records(seed: int = 42) -> List[BillingRecord]:
    rng=random.Random(seed); records=[]; march_days=[date(2026,3,d) for d in range(1,32)]
    def _rec(day,jtype,gpu,hours,partner,tags):
        return BillingRecord(str(uuid.UUID(int=rng.getrandbits(128))),day,jtype,gpu,round(hours,3),round(hours*GPU_RATES[gpu],4),partner,tags)
    for d in sorted(rng.sample(march_days,14)):
        h=max(0.5,min(3.5,rng.gauss(1.5,0.25)))
        records.append(_rec(d,"fine_tune","A100_80GB" if rng.random()<0.85 else "A100_80GB_spot",h,rng.choice(["internal","acme_robotics","blue_sky_labs"]),["gr00t",f"run{rng.randint(5,9)}"]))
    for d in sorted(rng.sample(march_days,8)):
        records.append(_rec(d,"dagger_collect","A100_40GB",max(0.3,min(1.8,rng.gauss(0.8,0.15))),rng.choice(["internal","nexgen_auto"]),["dagger","data-collection"]))
    for d in sorted(rng.sample(march_days,6)):
        records.append(_rec(d,"sdg","A100_80GB_spot",max(1.0,min(4.5,rng.gauss(2.1,0.4))),rng.choice(["internal","blue_sky_labs"]),["isaac-sim","domain-rand"]))
    for d in sorted(rng.sample(march_days,9)):
        records.append(_rec(d,"closed_loop_eval","A100_40GB",max(0.1,min(0.8,rng.gauss(0.3,0.06))),rng.choice(PARTNERS),["eval","closed-loop"]))
    for day_offset in range(12):
        d=date(2026,3,10+day_offset); h=12.0+rng.uniform(-0.5,0.5)
        cost_per_h=GPU_RATES["A100_80GB_spot"]*0.5
        records.append(BillingRecord(str(uuid.UUID(int=rng.getrandbits(128))),d,"inference","A100_80GB_spot",round(h,3),round(h*cost_per_h,4),"partner_demo",["serving","gr00t","production"]))
    for d in sorted(rng.sample(march_days,3)):
        records.append(_rec(d,"misc","A100_40GB",rng.uniform(0.1,0.5),"internal",["notebook","debug"]))
    records.sort(key=lambda r:r.date)
    return records

def compute_monthly_summary(records):
    spend=round(sum(r.cost_usd for r in records),2)
    days_elapsed=max((max(r.date for r in records)-date(2026,3,1)).days+1,1)
    forecast=round(spend*31/days_elapsed,2)
    return MonthlyBudget("2026-03",MONTHLY_BUDGET_USD,spend,forecast,ALERT_THRESHOLD_PCT)

def compute_breakdown_by_type(records):
    result={}
    for r in records:
        if r.job_type not in result: result[r.job_type]={"cost_usd":0.0,"hours":0.0,"count":0}
        result[r.job_type]["cost_usd"]+=r.cost_usd; result[r.job_type]["hours"]+=r.hours; result[r.job_type]["count"]+=1
    total=sum(v["cost_usd"] for v in result.values())
    for v in result.values():
        v["cost_usd"]=round(v["cost_usd"],2); v["hours"]=round(v["hours"],2); v["pct"]=round(100*v["cost_usd"]/total,1) if total else 0.0
    return dict(sorted(result.items(),key=lambda x:-x[1]["cost_usd"]))

def compute_breakdown_by_partner(records):
    result={}
    for r in records: result[r.partner_id]=round(result.get(r.partner_id,0.0)+r.cost_usd,4)
    total=sum(result.values())
    return {k:{"cost_usd":round(v,2),"pct":round(100*v/total,1) if total else 0.0} for k,v in sorted(result.items(),key=lambda x:-x[1])}

def _daily_spend_svg(records,width=760,height=180):
    daily={d:0.0 for d in range(1,32)}
    for r in records: daily[r.date.day]=round(daily.get(r.date.day,0.0)+r.cost_usd,4)
    values=[daily[d] for d in range(1,32)]; max_val=max(values) if max(values)>0 else 1.0
    pad_l,pad_r,pad_t,pad_b=40,12,16,32
    chart_w=width-pad_l-pad_r; chart_h=height-pad_t-pad_b; bar_w=chart_w/31; gap=max(1.0,bar_w*0.18)
    bars=[]
    for i,v in enumerate(values):
        bh=(v/max_val)*chart_h; x=pad_l+i*bar_w+gap/2; y=pad_t+chart_h-bh; w=bar_w-gap
        color="#3B82F6" if v<max_val*0.7 else "#F59E0B"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{bh:.1f}" fill="{color}" rx="2"><title>Mar {i+1}: ${v:.2f}</title></rect>')
    y_labels=[(pad_t+chart_h,"$0"),(pad_t+chart_h/2,f"${max_val/2:.0f}"),(pad_t,f"${max_val:.0f}")]
    y_ticks="".join(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" font-size="9" fill="#6B7280">{lbl}</text>' for y,lbl in y_labels)
    x_ticks="".join(f'<text x="{pad_l+(d-1)*bar_w+bar_w/2:.1f}" y="{height-6}" text-anchor="middle" font-size="9" fill="#6B7280">{d}</text>' for d in range(1,32,5))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="display:block;max-width:100%">'
            f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#D1D5DB" stroke-width="1"/>'
            f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#D1D5DB" stroke-width="1"/>'
            +"".join(bars)+y_ticks+x_ticks+"</svg>")

def _gauge_svg(pct,budget,spend,width=220,height=130):
    pct_c=min(pct,100.0); cx,cy,r=width//2,height-20,90
    def polar(deg): rad=math.radians(deg); return cx+r*math.cos(rad),cy-r*math.sin(rad)
    sx,sy=polar(180); ex,ey=polar(0)
    bg_arc=f'<path d="M {sx:.1f} {sy:.1f} A {r} {r} 0 0 1 {ex:.1f} {ey:.1f}" fill="none" stroke="#E5E7EB" stroke-width="18" stroke-linecap="round"/>'
    fill_deg=180*pct_c/100; fx,fy=polar(180-fill_deg)
    fc="#059669" if pct<70 else ("#F59E0B" if pct<ALERT_THRESHOLD_PCT else "#EF4444")
    fill_arc=f'<path d="M {sx:.1f} {sy:.1f} A {r} {r} 0 {"1" if fill_deg>180 else "0"} 1 {fx:.1f} {fy:.1f}" fill="none" stroke="{fc}" stroke-width="18" stroke-linecap="round"/>'
    label=(f'<text x="{cx}" y="{cy-12}" text-anchor="middle" font-size="22" font-weight="800" fill="{fc}">{pct_c:.1f}%</text>'
           f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="11" fill="#6B7280">of ${budget:,.0f} budget</text>'
           f'<text x="{cx}" y="{cy+26}" text-anchor="middle" font-size="10" fill="#9CA3AF">MTD: ${spend:,.2f}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">{bg_arc}{fill_arc}{label}</svg>'

def generate_billing_report(records,summary):
    by_type=compute_breakdown_by_type(records); by_partner=compute_breakdown_by_partner(records)
    spend_pct=round(100*summary.spend_usd/summary.budget_usd,1); remaining=round(summary.budget_usd-summary.spend_usd,2)
    alert_active=spend_pct>=summary.alert_threshold_pct
    kpis=[("MTD Spend",f"${summary.spend_usd:,.2f}","#1F2937"),("Forecast",f"${summary.forecast_usd:,.2f}","#2563EB"),("Remaining",f"${remaining:,.2f}","#059669" if remaining>0 else "#EF4444"),("Budget Alert","ALERT" if alert_active else "Within Budget","#EF4444" if alert_active else "#059669")]
    kpi_html="".join(f"<div class='kpi-box'><div class='kpi-val' style='color:{c}'>{v}</div><div class='kpi-lbl'>{lbl}</div></div>" for lbl,v,c in kpis)
    type_rows="".join(f"<tr><td>{jt.replace('_',' ').title()}</td><td>{info['count']}</td><td>{info['hours']:.1f}h</td><td>${info['cost_usd']:,.2f}</td><td><div style='display:flex;align-items:center;gap:8px'><div style='height:8px;border-radius:4px;background:#3B82F6;width:{min(info['pct'],100)*1.6:.0f}px'></div>{info['pct']:.1f}%</div></td></tr>" for jt,info in by_type.items())
    partner_rows="".join(f"<tr><td>{pid.replace('_',' ').title()}</td><td>${info['cost_usd']:,.2f}</td><td><div style='display:flex;align-items:center;gap:8px'><div style='height:8px;border-radius:4px;background:#8B5CF6;width:{min(info['pct'],100)*1.6:.0f}px'></div>{info['pct']:.1f}%</div></td></tr>" for pid,info in by_partner.items())
    daily_svg=_daily_spend_svg(records); gauge_svg=_gauge_svg(spend_pct,summary.budget_usd,summary.spend_usd)
    html=f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud \u2014 Billing Dashboard</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',Arial,sans-serif;background:#F3F4F6;color:#111827}}
.page{{max-width:980px;margin:32px auto;padding:0 16px 56px}}
h1{{font-size:1.6rem;font-weight:800;color:#1F2937;margin-bottom:4px}}.subtitle{{font-size:.9rem;color:#6B7280;margin-bottom:24px}}
.section-title{{font-size:.85rem;font-weight:700;color:#374151;letter-spacing:.07em;text-transform:uppercase;margin:28px 0 12px}}
.kpi-row{{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:8px}}
.kpi-box{{flex:1 1 180px;background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:18px 22px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
.kpi-val{{font-size:1.7rem;font-weight:800}}.kpi-lbl{{font-size:.78rem;color:#6B7280;margin-top:4px}}
.card{{background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:22px 24px;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:20px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
table{{width:100%;border-collapse:collapse;font-size:.875rem}}
th{{background:#1F2937;color:#F9FAFB;padding:9px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #F3F4F6}}tr:last-child td{{border-bottom:none}}tr:hover td{{background:#F9FAFB}}
.gauge-wrap{{display:flex;flex-direction:column;align-items:center;padding-top:8px}}
.footer{{text-align:center;margin-top:40px;font-size:.75rem;color:#9CA3AF;letter-spacing:.06em}}</style></head>
<body><div class="page">
<h1>OCI Robot Cloud \u2014 Billing Dashboard</h1>
<div class="subtitle">March 2026 &nbsp;\u00b7&nbsp; GR00T N1.6 &nbsp;\u00b7&nbsp; {len(records)} records &nbsp;\u00b7&nbsp; 2026-03-30</div>
<div class="section-title">Monthly KPIs</div>
<div class="kpi-row">{kpi_html}</div>
<div class="section-title">Daily Spend</div>
<div class="card"><div style="font-size:.8rem;color:#6B7280;margin-bottom:10px">Bar height = USD billed per day. Hover for exact value.</div>{daily_svg}</div>
<div class="section-title">Breakdown by Job Type &amp; Budget Gauge</div>
<div class="two-col">
<div class="card"><table><thead><tr><th>Job Type</th><th>Jobs</th><th>GPU-h</th><th>Cost</th><th>% Total</th></tr></thead><tbody>{type_rows}</tbody></table></div>
<div class="card"><div class="gauge-wrap"><div style="font-weight:700;font-size:.9rem;color:#374151;margin-bottom:12px">Budget Utilisation</div>{gauge_svg}
<div style="font-size:.78rem;color:#6B7280;margin-top:8px;text-align:center">Alert: {summary.alert_threshold_pct:.0f}% &nbsp;|&nbsp; Forecast: {round(100*summary.forecast_usd/summary.budget_usd,1)}%</div></div></div>
</div>
<div class="section-title">Breakdown by Partner</div>
<div class="card"><table><thead><tr><th>Partner</th><th>Cost (USD)</th><th>% Total</th></tr></thead><tbody>{partner_rows}</tbody></table></div>
<div class="footer">ORACLE CONFIDENTIAL &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Billing \u2014 March 2026</div>
</div></body></html>"""
    out_path="/tmp/oci_billing_dashboard.html"
    with open(out_path,"w",encoding="utf-8") as fh: fh.write(html)
    print(f"[billing] Dashboard saved \u2192 {out_path}")
    return html

def main():
    records=generate_billing_records(seed=42)
    summary=compute_monthly_summary(records)
    by_type=compute_breakdown_by_type(records); by_partner=compute_breakdown_by_partner(records)
    print(f"\n  OCI Robot Cloud \u2014 Billing Summary \u2014 March 2026 ({len(records)} records)\n")
    print(f"  {'Job Type':<22}  {'Jobs':>5}  {'GPU-h':>8}  {'Cost':>10}  {'%':>6}")
    print("  "+"-"*58)
    for jt,info in by_type.items():
        print(f"  {jt.replace('_',' ').title():<22}  {info['count']:>5}  {info['hours']:>8.1f}  ${info['cost_usd']:>9,.2f}  {info['pct']:>5.1f}%")
    tc=sum(i['cost_usd'] for i in by_type.values()); th=sum(i['hours'] for i in by_type.values()); tj=sum(i['count'] for i in by_type.values())
    print("  "+"-"*58+f"\n  {'TOTAL':<22}  {tj:>5}  {th:>8.1f}  ${tc:>9,.2f}  100.0%")
    print(f"\n  Budget: ${summary.budget_usd:,.2f}  MTD: ${summary.spend_usd:,.2f} ({round(100*summary.spend_usd/summary.budget_usd,1)}%)  Forecast: ${summary.forecast_usd:,.2f}")
    print("  Partner: "+"  ".join(f"{pid}=${info['cost_usd']:.2f}" for pid,info in by_partner.items()))
    generate_billing_report(records,summary)

if __name__ == "__main__": main()
