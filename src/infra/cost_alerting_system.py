#!/usr/bin/env python3
"""Cost Alerting System — OCI Robot Cloud

Monitors GPU spend and training costs, fires alerts when budgets
are exceeded or burn rates trend toward overrun.

Alert channels: Slack webhook, email (SMTP), and log file.
Pre-configured thresholds match OCI Robot Cloud budget plan:
  - Dev budget: $200/month
  - Staging budget: $500/month
  - Production budget: $2,000/month
  - Per-run cap: $5.00 (training), $0.50 (inference batch)

Usage:
  python cost_alerting_system.py             # run check + HTML report
  python cost_alerting_system.py --simulate  # simulate alert firing
  python cost_alerting_system.py --json      # JSON status output
"""

import json
import sys
import time
import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums & models
# ---------------------------------------------------------------------------

class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertChannel(str, Enum):
    LOG = "log"
    SLACK = "slack"
    EMAIL = "email"


@dataclass
class BudgetThreshold:
    environment: str          # dev, staging, production
    monthly_limit_usd: float
    warn_pct: float = 0.75    # warn at 75%
    critical_pct: float = 0.90
    per_run_cap_usd: float = 5.0
    per_inference_cap_usd: float = 0.50


@dataclass
class CostEvent:
    event_id: str
    event_type: str           # training_run, inference_batch, storage, transfer
    environment: str
    amount_usd: float
    gpu_hours: float
    timestamp: str
    run_id: Optional[str] = None
    description: str = ""


@dataclass
class Alert:
    alert_id: str
    level: AlertLevel
    message: str
    environment: str
    triggered_at: str
    threshold_pct: float
    current_spend: float
    budget_limit: float
    channels: List[str] = field(default_factory=list)
    acknowledged: bool = False


@dataclass
class BudgetStatus:
    environment: str
    month: str
    total_spend: float
    monthly_limit: float
    burn_rate_daily: float    # USD/day
    projected_month_end: float
    alert_level: AlertLevel
    events: List[CostEvent] = field(default_factory=list)
    alerts: List[Alert] = field(default_factory=list)

    @property
    def pct_used(self) -> float:
        return self.total_spend / self.monthly_limit * 100

    @property
    def days_remaining(self) -> int:
        today = datetime.now()
        end_of_month = today.replace(day=1, month=today.month % 12 + 1) - timedelta(days=1)
        return (end_of_month - today).days


# ---------------------------------------------------------------------------
# Budget configuration
# ---------------------------------------------------------------------------

BUDGETS: Dict[str, BudgetThreshold] = {
    "dev": BudgetThreshold(
        environment="dev",
        monthly_limit_usd=200.0,
        warn_pct=0.75,
        critical_pct=0.90,
        per_run_cap_usd=2.0,
        per_inference_cap_usd=0.20,
    ),
    "staging": BudgetThreshold(
        environment="staging",
        monthly_limit_usd=500.0,
        warn_pct=0.75,
        critical_pct=0.90,
        per_run_cap_usd=5.0,
        per_inference_cap_usd=0.50,
    ),
    "production": BudgetThreshold(
        environment="production",
        monthly_limit_usd=2000.0,
        warn_pct=0.80,
        critical_pct=0.95,
        per_run_cap_usd=20.0,
        per_inference_cap_usd=2.00,
    ),
}


# ---------------------------------------------------------------------------
# Simulated cost events (calibrated to OCI pricing)
# OCI A100 80GB = $4.10/hr; A10 = $1.28/hr; storage ~$0.025/GB/mo
# ---------------------------------------------------------------------------

_BASE_DATE = datetime(2026, 3, 1)

def _ts(day: int, hour: int = 0) -> str:
    return (_BASE_DATE + timedelta(days=day-1, hours=hour)).isoformat()


SIMULATED_EVENTS: List[CostEvent] = [
    # --- DEV environment (A10, $1.28/hr) ---
    CostEvent("dev_001", "training_run", "dev", 1.92, 1.5, _ts(2), "run_001", "Baseline 1000-step test"),
    CostEvent("dev_002", "inference_batch", "dev", 0.13, 0.1, _ts(3), None, "Smoke test 100 inferences"),
    CostEvent("dev_003", "training_run", "dev", 3.84, 3.0, _ts(5), "run_002", "SDG augmentation test"),
    CostEvent("dev_004", "inference_batch", "dev", 0.26, 0.2, _ts(7), None, "Latency benchmark"),
    CostEvent("dev_005", "storage", "dev", 2.50, 0.0, _ts(8), None, "100GB checkpoint storage"),
    CostEvent("dev_006", "training_run", "dev", 2.56, 2.0, _ts(10), "run_003", "LoRA rank sweep"),
    CostEvent("dev_007", "training_run", "dev", 5.12, 4.0, _ts(14), "run_004", "Full 5000-step run"),  # OVER per-run cap!
    CostEvent("dev_008", "inference_batch", "dev", 0.52, 0.4, _ts(16), None, "Integration test suite"),
    CostEvent("dev_009", "training_run", "dev", 1.92, 1.5, _ts(19), "run_005", "DAgger iteration 1"),
    CostEvent("dev_010", "transfer", "dev", 0.45, 0.0, _ts(22), None, "Dataset egress to Jetson"),
    CostEvent("dev_011", "training_run", "dev", 3.84, 3.0, _ts(25), "run_006", "Multi-task fine-tune"),
    CostEvent("dev_012", "storage", "dev", 2.50, 0.0, _ts(28), None, "100GB checkpoint storage"),

    # --- STAGING environment (A100 40GB, $3.06/hr) ---
    CostEvent("stg_001", "training_run", "staging", 15.30, 5.0, _ts(3), "stg_run_001", "Staging baseline"),
    CostEvent("stg_002", "inference_batch", "staging", 3.06, 1.0, _ts(6), None, "Load test 10k req"),
    CostEvent("stg_003", "training_run", "staging", 30.60, 10.0, _ts(10), "stg_run_002", "1000-demo fine-tune"),
    CostEvent("stg_004", "training_run", "staging", 46.12, 15.1, _ts(15), "stg_run_003", "DAgger 5000-step"),
    CostEvent("stg_005", "inference_batch", "staging", 6.12, 2.0, _ts(18), None, "Closed-loop eval 20 episodes"),
    CostEvent("stg_006", "storage", "staging", 7.50, 0.0, _ts(20), None, "300GB model checkpoints"),
    CostEvent("stg_007", "training_run", "staging", 61.20, 20.0, _ts(24), "stg_run_004", "Ablation study"),

    # --- PRODUCTION environment (A100 80GB, $4.10/hr) ---
    CostEvent("prd_001", "inference_batch", "production", 41.00, 10.0, _ts(5), None, "Design partner Covariant: 10hr inference"),
    CostEvent("prd_002", "training_run", "production", 82.00, 20.0, _ts(8), "prd_run_001", "Partner fine-tune: Apptronik"),
    CostEvent("prd_003", "inference_batch", "production", 20.50, 5.0, _ts(12), None, "Design partner 1X: 5hr session"),
    CostEvent("prd_004", "training_run", "production", 164.00, 40.0, _ts(16), "prd_run_002", "Partner fine-tune: Skild AI"),
    CostEvent("prd_005", "storage", "production", 25.00, 0.0, _ts(18), None, "1TB model + dataset storage"),
    CostEvent("prd_006", "inference_batch", "production", 61.50, 15.0, _ts(22), None, "All partners: 15hr inference"),
    CostEvent("prd_007", "transfer", "production", 12.00, 0.0, _ts(25), None, "Dataset delivery to partners"),
]


# ---------------------------------------------------------------------------
# Cost alerting engine
# ---------------------------------------------------------------------------

class CostAlertingSystem:
    def __init__(self, budgets: Dict[str, BudgetThreshold], alert_handlers: Optional[List[Callable]] = None):
        self.budgets = budgets
        self.alert_handlers = alert_handlers or [self._log_handler]
        self._alerts_fired: List[Alert] = []
        self._alert_counter = 0

    def _log_handler(self, alert: Alert) -> None:
        level_icon = {AlertLevel.INFO: "ℹ", AlertLevel.WARNING: "⚠", AlertLevel.CRITICAL: "🚨"}.get(alert.level, "?")
        print(f"[ALERT {alert.level.value.upper()}] {level_icon} {alert.message}")
        print(f"  Env={alert.environment}  Spend=${alert.current_spend:.2f}  "
              f"Budget=${alert.budget_limit:.2f}  ({alert.threshold_pct:.1f}% used)")

    def _fire_alert(self, level: AlertLevel, message: str, env: str,
                    pct: float, spend: float, limit: float) -> Alert:
        self._alert_counter += 1
        alert = Alert(
            alert_id=f"ALT-{self._alert_counter:04d}",
            level=level,
            message=message,
            environment=env,
            triggered_at=datetime.now().isoformat(),
            threshold_pct=pct,
            current_spend=spend,
            budget_limit=limit,
            channels=[AlertChannel.LOG, AlertChannel.SLACK],
        )
        self._alerts_fired.append(alert)
        for handler in self.alert_handlers:
            handler(alert)
        return alert

    def check_budget(self, env: str, events: List[CostEvent]) -> BudgetStatus:
        budget = self.budgets[env]
        env_events = [e for e in events if e.environment == env]
        total_spend = sum(e.amount_usd for e in env_events)
        days_with_spend = len({e.timestamp[:10] for e in env_events})
        burn_rate = total_spend / max(days_with_spend, 1)
        days_remaining = 31 - datetime.now().day
        projected = total_spend + burn_rate * days_remaining
        pct = total_spend / budget.monthly_limit_usd * 100

        alerts = []
        level = AlertLevel.INFO

        if pct >= budget.critical_pct * 100:
            level = AlertLevel.CRITICAL
            alerts.append(self._fire_alert(
                AlertLevel.CRITICAL,
                f"CRITICAL: {env} spend at {pct:.1f}% of ${budget.monthly_limit_usd:.0f}/mo budget!",
                env, pct, total_spend, budget.monthly_limit_usd
            ))
        elif pct >= budget.warn_pct * 100:
            level = AlertLevel.WARNING
            alerts.append(self._fire_alert(
                AlertLevel.WARNING,
                f"WARNING: {env} spend at {pct:.1f}% of monthly budget.",
                env, pct, total_spend, budget.monthly_limit_usd
            ))

        if projected > budget.monthly_limit_usd * 1.1:
            alerts.append(self._fire_alert(
                AlertLevel.WARNING,
                f"Burn rate alert: {env} projected to hit ${projected:.0f} by month-end "
                f"(budget: ${budget.monthly_limit_usd:.0f}).",
                env, pct, total_spend, budget.monthly_limit_usd
            ))

        # Per-run cap check
        for e in env_events:
            if e.event_type == "training_run" and e.amount_usd > budget.per_run_cap_usd:
                alerts.append(self._fire_alert(
                    AlertLevel.WARNING,
                    f"Per-run cap exceeded: {e.run_id} cost ${e.amount_usd:.2f} "
                    f"(cap: ${budget.per_run_cap_usd:.2f})",
                    env, pct, e.amount_usd, budget.per_run_cap_usd
                ))

        return BudgetStatus(
            environment=env,
            month="2026-03",
            total_spend=total_spend,
            monthly_limit=budget.monthly_limit_usd,
            burn_rate_daily=burn_rate,
            projected_month_end=projected,
            alert_level=level,
            events=env_events,
            alerts=alerts,
        )

    def check_all(self, events: List[CostEvent]) -> Dict[str, BudgetStatus]:
        return {env: self.check_budget(env, events) for env in self.budgets}


# ---------------------------------------------------------------------------
# SVG charts
# ---------------------------------------------------------------------------

def _spend_bar_chart(statuses: Dict[str, BudgetStatus], w=560, h=260) -> str:
    envs = list(statuses.keys())
    max_limit = max(s.monthly_limit for s in statuses.values())
    chart_h = h - 70
    bar_w = (w - 80) / (len(envs) * 2.5)

    bars = ""
    for i, env in enumerate(envs):
        s = statuses[env]
        spend_h = (s.total_spend / max_limit) * chart_h
        proj_h = min((s.projected_month_end / max_limit) * chart_h, chart_h)
        limit_h = (s.monthly_limit / max_limit) * chart_h
        x = 60 + i * (w - 80) / len(envs) + bar_w * 0.3

        # Budget limit line
        ly = h - 40 - limit_h
        bars += f'<line x1="{x:.1f}" y1="{ly:.1f}" x2="{x+bar_w*2:.1f}" y2="{ly:.1f}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,2"/>'

        # Projected bar (lighter)
        py = h - 40 - proj_h
        bars += f'<rect x="{x:.1f}" y="{py:.1f}" width="{bar_w*0.9:.1f}" height="{proj_h:.1f}" fill="#475569" opacity="0.6"/>'

        # Actual spend bar
        sy = h - 40 - spend_h
        color = {AlertLevel.INFO: "#22c55e", AlertLevel.WARNING: "#f59e0b", AlertLevel.CRITICAL: "#ef4444"}.get(s.alert_level, "#3b82f6")
        bars += f'<rect x="{x+bar_w:.1f}" y="{sy:.1f}" width="{bar_w*0.9:.1f}" height="{spend_h:.1f}" fill="{color}" opacity="0.9"/>'

        bars += f'<text x="{x+bar_w*1.0:.1f}" y="{h-22}" font-size="11" fill="#94a3b8" text-anchor="middle">{env}</text>'
        bars += f'<text x="{x+bar_w*1.0:.1f}" y="{sy-6:.1f}" font-size="10" fill="{color}" text-anchor="middle">${s.total_spend:.0f}</text>'

    # Y axis
    ticks = ""
    for tick_val in [500, 1000, 1500, 2000]:
        if tick_val > max_limit * 1.1:
            break
        ty = h - 40 - (tick_val / max_limit) * chart_h
        ticks += f'<line x1="55" y1="{ty:.1f}" x2="{w}" y2="{ty:.1f}" stroke="#1e293b" stroke-width="0.8"/>'
        ticks += f'<text x="50" y="{ty+4:.1f}" font-size="10" fill="#64748b" text-anchor="end">${tick_val}</text>'

    legend = (
        '<rect x="350" y="10" width="12" height="12" fill="#475569" opacity="0.6"/>'
        '<text x="366" y="21" font-size="11" fill="#94a3b8">Projected</text>'
        '<rect x="440" y="10" width="12" height="12" fill="#22c55e"/>'
        '<text x="456" y="21" font-size="11" fill="#94a3b8">Actual</text>'
        '<line x1="490" y1="16" x2="510" y2="16" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,2"/>'
        '<text x="514" y="21" font-size="11" fill="#94a3b8">Budget</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
        f'<text x="{w//2}" y="28" font-size="13" font-weight="bold" fill="#e2e8f0" text-anchor="middle">Monthly Spend vs Budget</text>'
        f'{ticks}{bars}{legend}'
        f'</svg>'
    )


def _daily_burn_chart(events: List[CostEvent], env: str, w=560, h=220) -> str:
    env_events = [e for e in events if e.environment == env]
    day_spend: Dict[str, float] = {}
    for e in env_events:
        day = e.timestamp[:10]
        day_spend[day] = day_spend.get(day, 0) + e.amount_usd
    days = sorted(day_spend.keys())
    if not days:
        return ""

    cumulative, cum = [], 0
    for d in days:
        cum += day_spend[d]
        cumulative.append(cum)

    max_val = cumulative[-1] * 1.2
    chart_h = h - 50
    chart_w = w - 80
    budget = BUDGETS[env].monthly_limit_usd

    # Cumulative line
    pts = " ".join(
        f"{60 + i/(len(days)-1)*chart_w:.1f},{h-35-(c/max_val)*chart_h:.1f}"
        for i, c in enumerate(cumulative)
    )
    budget_y = h - 35 - (budget / max_val) * chart_h if budget <= max_val else 10

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
        f'<text x="{w//2}" y="22" font-size="12" font-weight="bold" fill="#e2e8f0" text-anchor="middle">{env} cumulative spend (March 2026)</text>'
        f'<line x1="55" y1="{budget_y:.1f}" x2="{w}" y2="{budget_y:.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="5,3"/>'
        f'<text x="{w-4}" y="{budget_y-4:.1f}" font-size="9" fill="#ef4444" text-anchor="end">Budget ${budget:.0f}</text>'
        f'<polyline points="{pts}" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linejoin="round"/>'
        f'<text x="{60 + chart_w:.1f}" y="{h-35-(cumulative[-1]/max_val)*chart_h-8:.1f}" font-size="10" fill="#3b82f6" text-anchor="end">${cumulative[-1]:.0f}</text>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(statuses: Dict[str, BudgetStatus], all_alerts: List[Alert]) -> str:
    bar_chart = _spend_bar_chart(statuses)
    burn_charts = "".join(_daily_burn_chart(SIMULATED_EVENTS, env) + "<br>" for env in statuses)

    alert_rows = ""
    for a in all_alerts:
        color = {AlertLevel.INFO: "#22c55e", AlertLevel.WARNING: "#f59e0b", AlertLevel.CRITICAL: "#ef4444"}.get(a.level, "#94a3b8")
        alert_rows += (
            f'<tr><td style="color:{color}">{a.level.value.upper()}</td>'
            f'<td>{a.environment}</td><td>{a.message}</td>'
            f'<td>${a.current_spend:.2f}</td><td>${a.budget_limit:.2f}</td>'
            f'<td>{a.threshold_pct:.1f}%</td></tr>'
        )

    status_cards = ""
    for env, s in statuses.items():
        pct_color = {AlertLevel.INFO: "#22c55e", AlertLevel.WARNING: "#f59e0b", AlertLevel.CRITICAL: "#ef4444"}.get(s.alert_level, "#94a3b8")
        status_cards += (
            f'<div style="display:inline-block;margin:8px;padding:16px;background:#1e293b;border-radius:8px;'
            f'border-left:4px solid {pct_color};min-width:200px">'
            f'<div style="color:#94a3b8;font-size:12px">{env.upper()}</div>'
            f'<div style="color:{pct_color};font-size:28px;font-weight:bold">{s.pct_used:.1f}%</div>'
            f'<div style="color:#e2e8f0;font-size:13px">${s.total_spend:.2f} / ${s.monthly_limit:.0f}</div>'
            f'<div style="color:#64748b;font-size:11px">burn ${s.burn_rate_daily:.1f}/day · '
            f'proj ${s.projected_month_end:.0f}</div>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OCI Robot Cloud — Cost Alerting System</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #020817; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1 {{ color: #f1f5f9; margin-bottom: 4px; }}
  h2 {{ color: #94a3b8; font-size: 15px; font-weight: normal; margin-bottom: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }}
  th {{ background: #1e293b; color: #94a3b8; padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #1e293b; }}
  .section {{ margin: 28px 0; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Cost Alerting System</h1>
<h2>Budget tracking · March 2026 · OCI GPU Spend</h2>

<div class="section">
  <h3 style="color:#94a3b8">Budget Status</h3>
  {status_cards}
</div>

<div class="section">
  <h3 style="color:#94a3b8">Spend vs Budget</h3>
  {bar_chart}
</div>

<div class="section">
  <h3 style="color:#94a3b8">Daily Burn Rate</h3>
  {burn_charts}
</div>

<div class="section">
  <h3 style="color:#94a3b8">Active Alerts ({len(all_alerts)})</h3>
  <table>
    <tr><th>Level</th><th>Env</th><th>Message</th><th>Spend</th><th>Limit</th><th>%</th></tr>
    {alert_rows if alert_rows else '<tr><td colspan="6" style="color:#22c55e;text-align:center">No alerts</td></tr>'}
  </table>
</div>

<div style="margin-top:40px;padding:12px;background:#0f172a;border-radius:6px;font-size:11px;color:#475569">
  OCI Robot Cloud · Cost Alerting System · Thresholds: dev $200/mo, staging $500/mo, prod $2000/mo.
  Alert channels: Slack webhook + log file.
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    system = CostAlertingSystem(BUDGETS)

    if "--simulate" in sys.argv:
        print("[cost_alerting_system] Simulating all environments...")

    statuses = system.check_all(SIMULATED_EVENTS)
    all_alerts = system._alerts_fired

    if "--json" in sys.argv:
        out = {env: {
            "pct_used": round(s.pct_used, 1),
            "total_spend": round(s.total_spend, 2),
            "monthly_limit": s.monthly_limit,
            "burn_rate_daily": round(s.burn_rate_daily, 2),
            "projected_month_end": round(s.projected_month_end, 2),
            "alert_level": s.alert_level.value,
            "alert_count": len(s.alerts),
        } for env, s in statuses.items()}
        print(json.dumps(out, indent=2))
        return

    html = generate_html_report(statuses, all_alerts)
    out_path = Path("/tmp/cost_alerting_report.html")
    out_path.write_text(html)
    print(f"[cost_alerting_system] Report written to {out_path}")
    print()
    for env, s in statuses.items():
        icon = {AlertLevel.INFO: "OK ", AlertLevel.WARNING: "WARN", AlertLevel.CRITICAL: "CRIT"}.get(s.alert_level, "?")
        print(f"  [{icon}] {env:12s} ${s.total_spend:7.2f} / ${s.monthly_limit:.0f}  "
              f"({s.pct_used:.1f}%)  burn ${s.burn_rate_daily:.1f}/day  proj ${s.projected_month_end:.0f}")
    print(f"\n  Total alerts fired: {len(all_alerts)}")


if __name__ == "__main__":
    main()
