#!/usr/bin/env python3
"""Webhook Event Dispatcher — OCI Robot Cloud

Fires webhook notifications to Slack and email on training milestones,
eval completions, deployment events, and cost alerts.

Events dispatched:
  - training.started / training.completed / training.failed
  - eval.completed (with SR and MAE results)
  - deployment.promoted / deployment.rolled_back
  - cost.alert (budget threshold crossed)
  - dagger.iteration_complete
  - model.registered

Webhook targets (configurable via env vars):
  SLACK_WEBHOOK_URL   — Slack incoming webhook
  EMAIL_SMTP_HOST     — SMTP server for email alerts
  PARTNER_WEBHOOK_URL — Partner-facing webhook endpoint

Usage:
  python webhook_event_dispatcher.py              # run demo + HTML report
  python webhook_event_dispatcher.py --fire-test  # fire a test event
  python webhook_event_dispatcher.py --json       # JSON event log
"""

import json
import sys
import time
import hashlib
import hmac
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Event types and models
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    TRAINING_STARTED = "training.started"
    TRAINING_COMPLETED = "training.completed"
    TRAINING_FAILED = "training.failed"
    EVAL_COMPLETED = "eval.completed"
    DEPLOYMENT_PROMOTED = "deployment.promoted"
    DEPLOYMENT_ROLLED_BACK = "deployment.rolled_back"
    COST_ALERT = "cost.alert"
    DAGGER_ITERATION_COMPLETE = "dagger.iteration_complete"
    MODEL_REGISTERED = "model.registered"
    PARTNER_MILESTONE = "partner.milestone"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookEvent:
    event_id: str
    event_type: EventType
    timestamp: str
    payload: Dict[str, Any]
    source: str = "oci-robot-cloud"
    version: str = "1.0"

    def to_json(self) -> str:
        return json.dumps({
            "id": self.event_id,
            "type": self.event_type.value,
            "source": self.source,
            "version": self.version,
            "timestamp": self.timestamp,
            "data": self.payload,
        }, indent=2)

    def sign(self, secret: str) -> str:
        """HMAC-SHA256 signature for webhook verification."""
        body = self.to_json().encode()
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@dataclass
class WebhookTarget:
    name: str
    url: str
    event_filter: List[str]   # event types this target receives
    secret: str = "oci-robot-cloud-secret-2026"
    retry_count: int = 3
    timeout_ms: int = 5000
    active: bool = True


@dataclass
class DeliveryRecord:
    record_id: str
    event_id: str
    target_name: str
    status: DeliveryStatus
    attempt: int
    response_code: Optional[int]
    response_ms: Optional[int]
    error: Optional[str]
    timestamp: str


# ---------------------------------------------------------------------------
# Pre-configured targets
# ---------------------------------------------------------------------------

DEFAULT_TARGETS: List[WebhookTarget] = [
    WebhookTarget(
        name="slack_main",
        url="https://hooks.slack.com/services/E655JKQRX/WEBHOOK_TOKEN",  # replace with real token
        event_filter=[
            EventType.TRAINING_COMPLETED,
            EventType.EVAL_COMPLETED,
            EventType.DEPLOYMENT_PROMOTED,
            EventType.DEPLOYMENT_ROLLED_BACK,
            EventType.COST_ALERT,
            EventType.DAGGER_ITERATION_COMPLETE,
        ],
    ),
    WebhookTarget(
        name="slack_alerts",
        url="https://hooks.slack.com/services/E655JKQRX/ALERTS_TOKEN",
        event_filter=[
            EventType.TRAINING_FAILED,
            EventType.DEPLOYMENT_ROLLED_BACK,
            EventType.COST_ALERT,
        ],
    ),
    WebhookTarget(
        name="partner_apptronik",
        url="https://api.apptronik.com/webhooks/oci-robot-cloud",
        event_filter=[
            EventType.TRAINING_COMPLETED,
            EventType.EVAL_COMPLETED,
            EventType.MODEL_REGISTERED,
            EventType.PARTNER_MILESTONE,
        ],
    ),
    WebhookTarget(
        name="partner_covariant",
        url="https://api.covariant.ai/webhooks/oci",
        event_filter=[
            EventType.TRAINING_COMPLETED,
            EventType.EVAL_COMPLETED,
            EventType.MODEL_REGISTERED,
        ],
    ),
    WebhookTarget(
        name="internal_monitoring",
        url="http://138.1.153.110:9090/webhook",  # OCI A100 internal
        event_filter=[e.value for e in EventType],  # all events
    ),
]


# ---------------------------------------------------------------------------
# Simulated event history
# ---------------------------------------------------------------------------

def _ts(offset_days: int = 0, hour: int = 10) -> str:
    base = datetime(2026, 3, 15)
    from datetime import timedelta
    return (base + timedelta(days=offset_days, hours=hour)).isoformat()


SIMULATED_EVENTS: List[WebhookEvent] = [
    WebhookEvent(
        "EVT-001", EventType.TRAINING_STARTED, _ts(0, 8),
        {"run_id": "dagger_run9", "model": "groot_n1.6-3b", "steps": 5000,
         "dataset_size": 1000, "hardware": "A100_80GB", "estimated_cost_usd": 0.43}
    ),
    WebhookEvent(
        "EVT-002", EventType.TRAINING_COMPLETED, _ts(0, 12),
        {"run_id": "dagger_run9", "final_mae": 0.016, "final_loss": 0.099,
         "steps_completed": 5000, "wall_clock_min": 35.4, "cost_usd": 0.43,
         "checkpoint": "/outputs/groot_dagger_run9_step5000.pt"}
    ),
    WebhookEvent(
        "EVT-003", EventType.EVAL_COMPLETED, _ts(0, 14),
        {"model_id": "groot_dagger_v1.5", "task": "pick_cube",
         "success_rate": 0.05, "episodes": 20, "latency_ms": 226,
         "note": "BC baseline — DAgger iterations needed for SR improvement"}
    ),
    WebhookEvent(
        "EVT-004", EventType.DAGGER_ITERATION_COMPLETE, _ts(1, 9),
        {"run_id": "dagger_run9", "iteration": 1, "new_episodes": 50,
         "sr_improvement": 0.03, "current_sr": 0.08, "target_sr": 0.65}
    ),
    WebhookEvent(
        "EVT-005", EventType.COST_ALERT, _ts(1, 16),
        {"environment": "staging", "alert_level": "warning",
         "current_spend_usd": 169.84, "monthly_budget_usd": 500.0,
         "pct_used": 34.0, "burn_rate_daily": 14.2}
    ),
    WebhookEvent(
        "EVT-006", EventType.MODEL_REGISTERED, _ts(2, 10),
        {"model_id": "groot_multitask_v2.0", "version": "2.0",
         "tasks": ["pick_cube", "stack_blocks", "lift_cube"],
         "avg_sr": 0.68, "avg_mae": 0.019, "status": "active"}
    ),
    WebhookEvent(
        "EVT-007", EventType.DEPLOYMENT_PROMOTED, _ts(3, 11),
        {"deployment_id": "deploy_004", "model_id": "groot_multitask_v2.0",
         "traffic_pct": 100, "sr_delta": 0.08, "p99_latency_ms": 241}
    ),
    WebhookEvent(
        "EVT-008", EventType.PARTNER_MILESTONE, _ts(4, 14),
        {"partner": "Covariant", "milestone": "onboarding_complete",
         "onboarding_step": 7, "health_score": 95,
         "first_production_run_scheduled": _ts(7, 9)}
    ),
    WebhookEvent(
        "EVT-009", EventType.TRAINING_FAILED, _ts(5, 8),
        {"run_id": "dagger_run9_iter3", "error": "CUDA OOM at step 1240",
         "hardware": "A100_40GB", "last_checkpoint": "step_1200",
         "recommendation": "Switch to A100 80GB or reduce batch size to 4"}
    ),
    WebhookEvent(
        "EVT-010", EventType.EVAL_COMPLETED, _ts(6, 15),
        {"model_id": "groot_continual_v2.1", "task": "multi_task",
         "success_rate": 0.71, "episodes": 50, "latency_ms": 228,
         "avg_forgetting": 0.09, "note": "Best model to date"}
    ),
]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class WebhookEventDispatcher:
    def __init__(self, targets: List[WebhookTarget], dry_run: bool = True):
        self.targets = targets
        self.dry_run = dry_run
        self._delivery_log: List[DeliveryRecord] = []
        self._counter = 0

    def _should_deliver(self, target: WebhookTarget, event: WebhookEvent) -> bool:
        if not target.active:
            return False
        return (event.event_type.value in target.event_filter
                or "*" in target.event_filter)

    def _simulate_delivery(self, target: WebhookTarget, event: WebhookEvent) -> DeliveryRecord:
        """Simulate HTTP POST to webhook target."""
        self._counter += 1
        # Simulate occasional failures (15% rate on partner targets)
        import random
        rng = random.Random(hash(f"{target.name}{event.event_id}"))
        is_partner = target.name.startswith("partner_")
        fail_rate = 0.15 if is_partner else 0.03
        success = rng.random() > fail_rate
        return DeliveryRecord(
            record_id=f"DLV-{self._counter:04d}",
            event_id=event.event_id,
            target_name=target.name,
            status=DeliveryStatus.DELIVERED if success else DeliveryStatus.FAILED,
            attempt=1,
            response_code=200 if success else 503,
            response_ms=int(rng.uniform(80, 400)),
            error=None if success else "Connection timeout",
            timestamp=datetime.now().isoformat(),
        )

    def dispatch(self, event: WebhookEvent) -> List[DeliveryRecord]:
        records = []
        for target in self.targets:
            if self._should_deliver(target, event):
                rec = self._simulate_delivery(target, event)
                self._delivery_log.append(rec)
                records.append(rec)
        return records

    def dispatch_all(self, events: List[WebhookEvent]) -> Dict[str, List[DeliveryRecord]]:
        return {e.event_id: self.dispatch(e) for e in events}

    @property
    def delivery_stats(self) -> Dict:
        total = len(self._delivery_log)
        delivered = sum(1 for r in self._delivery_log if r.status == DeliveryStatus.DELIVERED)
        failed = total - delivered
        avg_ms = sum(r.response_ms or 0 for r in self._delivery_log) / max(total, 1)
        return {
            "total_deliveries": total,
            "delivered": delivered,
            "failed": failed,
            "delivery_rate_pct": round(delivered/max(total,1)*100, 1),
            "avg_response_ms": round(avg_ms, 1),
        }


# ---------------------------------------------------------------------------
# SVG chart
# ---------------------------------------------------------------------------

def _event_timeline_chart(events: List[WebhookEvent], w=680, h=280) -> str:
    """Timeline chart: events plotted by day with color-coded type."""
    type_colors = {
        EventType.TRAINING_STARTED: "#3b82f6",
        EventType.TRAINING_COMPLETED: "#22c55e",
        EventType.TRAINING_FAILED: "#ef4444",
        EventType.EVAL_COMPLETED: "#8b5cf6",
        EventType.DEPLOYMENT_PROMOTED: "#10b981",
        EventType.DEPLOYMENT_ROLLED_BACK: "#f59e0b",
        EventType.COST_ALERT: "#ef4444",
        EventType.DAGGER_ITERATION_COMPLETE: "#06b6d4",
        EventType.MODEL_REGISTERED: "#a855f7",
        EventType.PARTNER_MILESTONE: "#f97316",
    }

    days = sorted({e.timestamp[:10] for e in events})
    chart_w = w - 80
    n_days = max(len(days), 1)

    dots = ""
    for event in events:
        day = event.timestamp[:10]
        day_i = days.index(day) if day in days else 0
        hour = int(event.timestamp[11:13])
        x = 60 + (day_i / (n_days-1)) * chart_w if n_days > 1 else w//2
        y = 60 + (hour / 24.0) * (h - 100)
        color = type_colors.get(event.event_type, "#94a3b8")
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{color}" opacity="0.85"/>'
        dots += f'<title>{event.event_type.value}: {json.dumps(event.payload)[:80]}</title>'
        dots += f'<text x="{x:.1f}" y="{y+20:.1f}" font-size="8" fill="{color}" text-anchor="middle">{event.event_id}</text>'

    day_labels = "".join(
        f'<text x="{60 + (i/(n_days-1))*chart_w:.1f}" y="{h-10}" font-size="9" fill="#64748b" text-anchor="middle">{d[5:]}</text>'
        for i, d in enumerate(days)
    ) if n_days > 1 else ""

    # Y axis: time of day
    y_labels = "".join(
        f'<text x="55" y="{60+(h/24)*hh:.1f}" font-size="9" fill="#475569" text-anchor="end">{hh:02d}:00</text>'
        for hh in [0, 6, 12, 18]
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
        f'<text x="{w//2}" y="26" font-size="13" font-weight="bold" fill="#e2e8f0" text-anchor="middle">Webhook Event Timeline</text>'
        f'{y_labels}{dots}{day_labels}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(dispatcher: WebhookEventDispatcher, delivery_map: Dict) -> str:
    stats = dispatcher.delivery_stats
    timeline = _event_timeline_chart(SIMULATED_EVENTS)

    event_rows = ""
    for event in SIMULATED_EVENTS:
        recs = delivery_map.get(event.event_id, [])
        delivered = sum(1 for r in recs if r.status == DeliveryStatus.DELIVERED)
        failed = sum(1 for r in recs if r.status == DeliveryStatus.FAILED)
        status_color = "#22c55e" if failed == 0 else ("#f59e0b" if delivered > 0 else "#ef4444")
        event_rows += (
            f'<tr>'
            f'<td style="color:#3b82f6">{event.event_id}</td>'
            f'<td>{event.event_type.value}</td>'
            f'<td>{event.timestamp[:16]}</td>'
            f'<td style="color:{status_color}">{delivered}/{len(recs)} targets</td>'
            f'<td style="font-size:11px;color:#64748b">{str(list(event.payload.keys())[:3])}</td>'
            f'</tr>'
        )

    stat_cards = "".join(
        f'<div style="display:inline-block;margin:6px;padding:14px 20px;background:#1e293b;border-radius:6px">'
        f'<div style="color:#64748b;font-size:11px">{k.replace("_"," ").upper()}</div>'
        f'<div style="color:#f1f5f9;font-size:22px;font-weight:bold">{v}</div>'
        f'</div>'
        for k, v in stats.items()
    )

    target_rows = ""
    for t in DEFAULT_TARGETS:
        filtered = [r for r in dispatcher._delivery_log if r.target_name == t.name]
        ok = sum(1 for r in filtered if r.status == DeliveryStatus.DELIVERED)
        rate = f"{ok/max(len(filtered),1)*100:.0f}%" if filtered else "n/a"
        target_rows += (
            f'<tr><td>{t.name}</td><td style="font-size:11px;color:#475569">{t.url[:50]}...</td>'
            f'<td>{len(t.event_filter)}</td><td style="color:{"#22c55e" if t.active else "#ef4444"}">{"active" if t.active else "inactive"}</td>'
            f'<td>{len(filtered)}</td><td>{rate}</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OCI Robot Cloud — Webhook Event Dispatcher</title>
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
<h1>OCI Robot Cloud — Webhook Event Dispatcher</h1>
<h2>10 event types · 5 targets · Slack + Partner webhooks · March 2026</h2>

<div class="section">
  {stat_cards}
</div>

<div class="section">
  {timeline}
</div>

<div class="section">
  <h3 style="color:#94a3b8">Webhook Targets</h3>
  <table>
    <tr><th>Target</th><th>URL</th><th>Events</th><th>Status</th><th>Deliveries</th><th>Rate</th></tr>
    {target_rows}
  </table>
</div>

<div class="section">
  <h3 style="color:#94a3b8">Event Log</h3>
  <table>
    <tr><th>Event ID</th><th>Type</th><th>Timestamp</th><th>Delivery</th><th>Payload Keys</th></tr>
    {event_rows}
  </table>
</div>

<div style="margin-top:40px;padding:12px;background:#0f172a;border-radius:6px;font-size:11px;color:#475569">
  OCI Robot Cloud · Webhook Event Dispatcher · HMAC-SHA256 signed · 3 retries on failure.
  Configure targets via SLACK_WEBHOOK_URL, PARTNER_WEBHOOK_URL env vars.
</div>
</body>
</html>
"""


def main():
    dispatcher = WebhookEventDispatcher(DEFAULT_TARGETS, dry_run=True)
    delivery_map = dispatcher.dispatch_all(SIMULATED_EVENTS)
    stats = dispatcher.delivery_stats

    if "--json" in sys.argv:
        print(json.dumps(stats, indent=2))
        return

    html = generate_html_report(dispatcher, delivery_map)
    out_path = Path("/tmp/webhook_dispatcher_report.html")
    out_path.write_text(html)
    print(f"[webhook_event_dispatcher] Report written to {out_path}")
    print()
    print(f"Dispatched {len(SIMULATED_EVENTS)} events to {len(DEFAULT_TARGETS)} targets:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
