"""partner_webhook_service.py — Webhook notification service for OCI Robot Cloud design partners.
OCI Robot Cloud | Port 8088 | HMAC-SHA256 | Oracle Confidential
"""
from __future__ import annotations
import hashlib, hmac, json, random, time, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

PORT = 8088
EVENT_TYPES = ["training_complete", "eval_done", "drift_alert", "checkpoint_promoted", "trial_expiring"]
DELIVERY_STATUS = ("delivered", "failed", "pending", "retrying")
SEED_PARTNERS = [
    {"name": "Covariant", "tier": "enterprise", "events": EVENT_TYPES, "url": "https://hooks.covariant.ai/oci-robot-cloud", "secret": "cvt_secret_prod_a7f2c1", "contact": "integrations@covariant.ai"},
    {"name": "Apptronik", "tier": "growth", "events": ["training_complete", "eval_done"], "url": "https://webhooks.apptronik.com/oci-training", "secret": "apt_secret_prod_b3d9e2", "contact": "platform@apptronik.com"},
    {"name": "1X Technologies", "tier": "growth", "events": ["eval_done", "drift_alert"], "url": "https://api.1x.tech/callbacks/oci", "secret": "onex_secret_prod_c5f8g4", "contact": "cloud@1x.tech"},
]
MAX_RETRIES = 3

@dataclass
class Webhook:
    id: str; partner_name: str; tier: str; url: str; secret: str; contact: str
    subscribed_events: List[str]; active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_delivery_at: Optional[str] = None; delivery_success_count: int = 0; delivery_failure_count: int = 0

@dataclass
class DeliveryRecord:
    id: str; webhook_id: str; partner_name: str; event_type: str; status: str
    attempt: int; payload_summary: str; response_code: Optional[int]
    latency_ms: Optional[float]; timestamp: str; error: Optional[str] = None

@dataclass
class WebhookStore:
    webhooks: Dict[str, Webhook] = field(default_factory=dict)
    deliveries: List[DeliveryRecord] = field(default_factory=list)

def sign_payload(secret: str, payload_bytes: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

def verify_signature(secret: str, payload_bytes: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(secret, payload_bytes), signature)

_SAMPLE_PAYLOADS: Dict[str, Dict[str, Any]] = {
    "training_complete": {"model": "groot_n16", "run_id": "run-dagger-005", "steps": 5000, "final_loss": 0.099, "duration_min": 35.4, "checkpoint": "ckpt-5000"},
    "eval_done": {"model": "groot_n16", "checkpoint": "ckpt-5000", "success_rate": 0.65, "episodes": 20, "mean_latency_ms": 231.0, "task": "pick_and_place"},
    "drift_alert": {"model": "groot_n16", "alert_level": "ALERT", "composite_score": 0.34, "kl_divergence": 0.22, "psi_score": 0.19, "message": "Outdoor deployment domain shift detected"},
    "checkpoint_promoted": {"checkpoint": "ckpt-5000", "promoted_to": "production", "success_rate_delta": 0.12},
    "trial_expiring": {"partner": "Apptronik", "trial_end": "2026-04-15T00:00:00Z", "days_remaining": 16, "usage_pct": 78},
}

def _simulate_delivery(wh: Webhook, event_type: str, rng: random.Random, attempt: int = 1) -> DeliveryRecord:
    payload = dict(_SAMPLE_PAYLOADS.get(event_type, {})); payload["event"] = event_type; payload["webhook_id"] = wh.id
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    fail_rate = 0.08 if wh.tier == "enterprise" else 0.18; succeeded = rng.random() > fail_rate
    latency_ms = rng.gauss(110, 25) if succeeded else rng.gauss(3000, 500)
    code = 200 if succeeded else rng.choice([500, 502, 503, 408])
    status = "delivered" if succeeded else ("failed" if attempt >= MAX_RETRIES else "retrying")
    return DeliveryRecord(id=str(uuid.uuid4())[:8], webhook_id=wh.id, partner_name=wh.partner_name,
        event_type=event_type, status=status, attempt=attempt,
        payload_summary=f"{event_type} → {wh.partner_name} (attempt {attempt})",
        response_code=code, latency_ms=round(latency_ms, 1), timestamp=datetime.utcnow().isoformat() + "Z",
        error=None if succeeded else f"HTTP {code} upstream error")

def build_store() -> WebhookStore:
    store = WebhookStore(); rng = random.Random(42); base_ts = datetime(2026, 3, 1)
    for p in SEED_PARTNERS:
        wid = str(uuid.UUID(int=rng.getrandbits(128)))[:8]
        store.webhooks[wid] = Webhook(id=wid, partner_name=p["name"], tier=p["tier"], url=p["url"], secret=p["secret"], contact=p["contact"], subscribed_events=list(p["events"]))
    wh_list = list(store.webhooks.values())
    for day_off in sorted(rng.uniform(0, 30) for _ in range(20)):
        wh = rng.choice(wh_list); event_type = rng.choice(wh.subscribed_events)
        ts_obj = base_ts + timedelta(days=day_off); rec = _simulate_delivery(wh, event_type, rng); rec.timestamp = ts_obj.isoformat() + "Z"
        if rec.status == "retrying":
            for a in range(2, MAX_RETRIES + 1):
                retry_rec = _simulate_delivery(wh, event_type, rng, attempt=a); retry_rec.timestamp = (ts_obj + timedelta(seconds=2 ** a * 10)).isoformat() + "Z"
                store.deliveries.append(retry_rec)
                if retry_rec.status == "delivered": rec = retry_rec; break
                rec = retry_rec
        store.deliveries.append(rec)
        if rec.status == "delivered": wh.delivery_success_count += 1; wh.last_delivery_at = rec.timestamp
        else: wh.delivery_failure_count += 1
    store.deliveries.sort(key=lambda d: d.timestamp, reverse=True)
    return store

def generate_html_report(store: WebhookStore) -> str:
    all_recs = store.deliveries; total = len(all_recs)
    deliv = sum(1 for r in all_recs if r.status == "delivered"); failed = sum(1 for r in all_recs if r.status == "failed")
    pct = f"{100 * deliv / total:.1f}%" if total > 0 else "N/A"
    status_colors = {"delivered": "#22c55e", "failed": "#ef4444", "retrying": "#fb923c", "pending": "#facc15"}
    delivery_rows = "".join(f'<tr><td style="color:#94a3b8">{r.timestamp[:16]}</td><td>{r.partner_name}</td><td style="color:#a78bfa">{r.event_type}</td><td style="color:{status_colors.get(r.status,"#94a3b8")};font-weight:700">{r.status.upper()}</td><td>{r.response_code}</td><td>{r.latency_ms:.0f}ms</td><td style="color:#64748b">{r.error or "-"}</td></tr>' for r in store.deliveries[:20])
    wh_rows = "".join(f'<tr><td>{wh.partner_name}</td><td>{wh.tier}</td><td style="color:#22c55e">{wh.delivery_success_count}</td><td style="color:#ef4444">{wh.delivery_failure_count}</td><td style="word-break:break-all">{wh.url}</td></tr>' for wh in store.webhooks.values())
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'/><title>Partner Webhook Service</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;padding:24px}}h1{{color:#C74634}}h2{{color:#C74634;font-size:1rem;text-transform:uppercase;margin:24px 0 8px}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px}}.card{{background:#1e293b;border-radius:8px;padding:14px 20px;min-width:130px}}.card .val{{font-size:1.6rem;font-weight:700;margin:4px 0}}.card .lbl{{color:#64748b;font-size:.8rem}}table{{border-collapse:collapse;width:100%;font-size:.85rem}}th{{color:#64748b;text-align:left;padding:6px 10px;border-bottom:1px solid #1e293b}}td{{padding:6px 10px;border-bottom:1px solid #1e293b}}</style></head><body>
<h1>OCI Robot Cloud — Partner Webhook Service</h1><p style="color:#64748b">HMAC-SHA256 | Port {PORT} | Design Partner Notifications</p>
<div class="cards"><div class="card"><div class="lbl">Partners</div><div class="val">{len(store.webhooks)}</div></div><div class="card"><div class="lbl">Deliveries</div><div class="val">{total}</div></div><div class="card"><div class="lbl">Delivered</div><div class="val" style="color:#22c55e">{deliv}</div></div><div class="card"><div class="lbl">Failed</div><div class="val" style="color:#ef4444">{failed}</div></div><div class="card"><div class="lbl">Success Rate</div><div class="val">{pct}</div></div></div>
<h2>Registered Partners</h2><table><tr><th>Partner</th><th>Tier</th><th>Delivered</th><th>Failed</th><th>URL</th></tr>{wh_rows}</table>
<h2>Recent Deliveries</h2><table><tr><th>Timestamp</th><th>Partner</th><th>Event</th><th>Status</th><th>HTTP</th><th>Latency</th><th>Error</th></tr>{delivery_rows}</table>
<div style="margin-top:40px;color:#475569;font-size:.75rem">Oracle Confidential | OCI Robot Cloud 2026</div></body></html>"""

def build_app(store: WebhookStore):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
        from pydantic import BaseModel
    except ImportError: return None
    app = FastAPI(title="OCI Robot Cloud — Partner Webhook Service", version="1.0.0")
    class SubscribeRequest(BaseModel):
        partner_name: str; tier: str = "starter"; url: str; secret: str; contact: str; subscribed_events: List[str]
    class EmitRequest(BaseModel):
        event_type: str; payload: Optional[Dict[str, Any]] = None
    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return generate_html_report(store)
    @app.get("/webhooks")
    def list_webhooks(): return {"count": len(store.webhooks), "webhooks": [asdict(wh) for wh in store.webhooks.values()]}
    @app.post("/webhooks", status_code=201)
    def subscribe(req: SubscribeRequest):
        wid = str(uuid.uuid4())[:8]
        wh = Webhook(id=wid, partner_name=req.partner_name, tier=req.tier, url=req.url, secret=req.secret, contact=req.contact, subscribed_events=req.subscribed_events)
        store.webhooks[wid] = wh; return asdict(wh)
    @app.get("/webhooks/{webhook_id}")
    def get_webhook(webhook_id: str):
        wh = store.webhooks.get(webhook_id)
        if not wh: raise HTTPException(status_code=404, detail="webhook not found")
        return asdict(wh)
    @app.delete("/webhooks/{webhook_id}/unsubscribe")
    def unsubscribe(webhook_id: str):
        wh = store.webhooks.get(webhook_id)
        if not wh: raise HTTPException(status_code=404, detail="webhook not found")
        wh.active = False; return {"status": "unsubscribed", "webhook_id": webhook_id}
    @app.post("/events/emit")
    def emit_event(req: EmitRequest):
        if req.event_type not in EVENT_TYPES: raise HTTPException(status_code=400, detail=f"unknown event: {req.event_type}")
        rng = random.Random(); sent = []
        for wh in store.webhooks.values():
            if not wh.active or req.event_type not in wh.subscribed_events: continue
            rec = _simulate_delivery(wh, req.event_type, rng); store.deliveries.insert(0, rec)
            if rec.status == "delivered": wh.delivery_success_count += 1; wh.last_delivery_at = rec.timestamp
            else: wh.delivery_failure_count += 1
            sent.append(asdict(rec))
        return {"event_type": req.event_type, "dispatched": len(sent), "records": sent}
    @app.get("/deliveries")
    def list_deliveries(limit: int = 50): return {"count": min(limit, len(store.deliveries)), "deliveries": [asdict(r) for r in store.deliveries[:limit]]}
    return app

def main():
    print("=" * 70); print("OCI Robot Cloud — Partner Webhook Service"); print("=" * 70)
    store = build_store(); all_recs = store.deliveries; total = len(all_recs)
    deliv = sum(1 for r in all_recs if r.status == "delivered"); pct = 100 * deliv / total if total > 0 else 0
    print(f"Partners: {len(store.webhooks)} | Deliveries: {total} | Success: {deliv} ({pct:.1f}%)")
    for wh in store.webhooks.values(): print(f"  {wh.partner_name:<20} {wh.tier:<12} delivered={wh.delivery_success_count} failed={wh.delivery_failure_count}")
    html_path = "/tmp/partner_webhook_service_report.html"
    with open(html_path, "w", encoding="utf-8") as fh: fh.write(generate_html_report(store))
    print(f"HTML report: {html_path}")
    app = build_app(store)
    if app:
        import uvicorn; uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: print("(FastAPI not installed)")

if __name__ == "__main__":
    main()
