"""
customer_churn_predictor_v2.py
OCI Robot Cloud — Customer Churn Prediction Service (v2)
Port: 8082

Predicts which design partners are at risk of churning based on
engagement signals, SR trends, and billing patterns.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uvicorn

app = FastAPI(
    title="OCI Robot Cloud — Customer Churn Predictor v2",
    version="2.0.0",
    description="ML-style churn scoring for design partners",
)


class ChurnSignal(BaseModel):
    partner_id: str
    dimension: str
    raw_value: float
    normalized_score: float
    weight: float
    contribution: float


class ChurnPrediction(BaseModel):
    partner_id: str
    churn_score: float
    risk_level: str
    signals: List[ChurnSignal]
    arr_at_risk_usd: float
    recommended_action: str
    last_updated: str


class SummaryResponse(BaseModel):
    total_arr_at_risk_usd: float
    total_pipeline_arr_usd: float
    pct_pipeline_at_risk: float
    count_by_risk_level: dict
    avg_churn_score: float


WEIGHTS = {
    "sr_trend":          0.25,
    "days_since_last_run": 0.20,
    "dagger_engagement": 0.15,
    "data_freshness":    0.15,
    "support_tickets":   0.10,
    "billing_trend":     0.10,
    "nps_score":         0.05,
}

PARTNER_RAW_SIGNALS = {
    "covariant": {
        "sr_trend":            +0.30,
        "days_since_last_run":  1,
        "dagger_engagement":    1,
        "data_freshness":       1,
        "support_tickets":      0,
        "billing_trend":       +0.25,
        "nps_score":            9,
    },
    "apptronik": {
        "sr_trend":            +0.00,
        "days_since_last_run":  8,
        "dagger_engagement":    0,
        "data_freshness":       9,
        "support_tickets":      0,
        "billing_trend":       +0.05,
        "nps_score":            7,
    },
    "1x_technologies": {
        "sr_trend":            +0.05,
        "days_since_last_run": 12,
        "dagger_engagement":    0,
        "data_freshness":      15,
        "support_tickets":      1,
        "billing_trend":       -0.05,
        "nps_score":            6,
    },
    "skild_ai": {
        "sr_trend":            -0.10,
        "days_since_last_run": 18,
        "dagger_engagement":    0,
        "data_freshness":      20,
        "support_tickets":      2,
        "billing_trend":       -0.20,
        "nps_score":            5,
    },
    "physical_intelligence": {
        "sr_trend":            -0.30,
        "days_since_last_run": 14,
        "dagger_engagement":    0,
        "data_freshness":      14,
        "support_tickets":      1,
        "billing_trend":       -0.40,
        "nps_score":            4,
    },
}

PARTNER_GPU_HOURS_MONTHLY = {
    "covariant":             500,
    "apptronik":             240,
    "1x_technologies":       195,
    "skild_ai":              140,
    "physical_intelligence":  11,
}


def normalize_sr_trend(v: float) -> float:
    clamped = max(-0.30, min(0.30, v))
    return round((0.30 - clamped) / 0.60, 4)

def normalize_days_since_last_run(v: float) -> float:
    return round(min(v / 21.0, 1.0), 4)

def normalize_dagger_engagement(v: float) -> float:
    return round(1.0 - float(v), 4)

def normalize_data_freshness(v: float) -> float:
    return round(min(v / 21.0, 1.0), 4)

def normalize_support_tickets(v: float) -> float:
    return round(min(v / 3.0, 1.0), 4)

def normalize_billing_trend(v: float) -> float:
    clamped = max(-0.40, min(0.40, v))
    return round((0.40 - clamped) / 0.80, 4)

def normalize_nps_score(v: float) -> float:
    return round(1.0 - min(max(v, 0.0), 10.0) / 10.0, 4)


NORMALIZERS = {
    "sr_trend":            normalize_sr_trend,
    "days_since_last_run": normalize_days_since_last_run,
    "dagger_engagement":   normalize_dagger_engagement,
    "data_freshness":      normalize_data_freshness,
    "support_tickets":     normalize_support_tickets,
    "billing_trend":       normalize_billing_trend,
    "nps_score":           normalize_nps_score,
}

RISK_THRESHOLDS = [
    (0.00, 0.20, "safe"),
    (0.20, 0.40, "low"),
    (0.40, 0.60, "medium"),
    (0.60, 0.80, "high"),
    (0.80, 1.01, "critical"),
]

RISK_COLORS = {
    "safe":     "#22c55e",
    "low":      "#84cc16",
    "medium":   "#f59e0b",
    "high":     "#ef4444",
    "critical": "#7f1d1d",
}

RECOMMENDED_ACTIONS = {
    "covariant":             "Maintain momentum — schedule Q2 expansion call, propose multi-task upgrade.",
    "apptronik":             "Re-engage: invite to DAgger beta, share SR improvement case study from covariant.",
    "1x_technologies":       "CSM outreach within 72h — offer free DAgger onboarding session + 20 GPU-hr credit.",
    "skild_ai":              "Escalate to SA — resolve open P1 ticket immediately, schedule exec sponsor call.",
    "physical_intelligence": "Red alert: assign dedicated CSE, waive onboarding fee, co-develop first task together.",
}


def risk_level(score: float) -> str:
    for lo, hi, label in RISK_THRESHOLDS:
        if lo <= score < hi:
            return label
    return "critical"


def arr_at_risk(partner_id: str) -> float:
    hours = PARTNER_GPU_HOURS_MONTHLY.get(partner_id, 0)
    return round(hours * 4.10 * 12, 2)


def compute_prediction(partner_id: str, raw: dict) -> ChurnPrediction:
    signals = []
    total_score = 0.0

    for dim, weight in WEIGHTS.items():
        raw_val = raw.get(dim, 0.0)
        norm_fn = NORMALIZERS[dim]
        norm_score = norm_fn(raw_val)
        contribution = round(norm_score * weight, 5)
        total_score += contribution
        signals.append(ChurnSignal(
            partner_id=partner_id,
            dimension=dim,
            raw_value=raw_val,
            normalized_score=norm_score,
            weight=weight,
            contribution=contribution,
        ))

    churn_score = round(min(total_score, 1.0), 4)
    return ChurnPrediction(
        partner_id=partner_id,
        churn_score=churn_score,
        risk_level=risk_level(churn_score),
        signals=signals,
        arr_at_risk_usd=arr_at_risk(partner_id),
        recommended_action=RECOMMENDED_ACTIONS.get(partner_id, "No action defined."),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


_predictions: dict[str, ChurnPrediction] = {}


def _refresh_all() -> None:
    global _predictions
    _predictions = {
        pid: compute_prediction(pid, raw)
        for pid, raw in PARTNER_RAW_SIGNALS.items()
    }


_refresh_all()


def build_dashboard() -> str:
    sorted_preds = sorted(_predictions.values(), key=lambda p: p.churn_score, reverse=True)
    total_arr = sum(p.arr_at_risk_usd for p in sorted_preds if p.risk_level in ("high", "critical", "medium"))
    all_arr = sum(p.arr_at_risk_usd for p in sorted_preds)
    pct = round(total_arr / all_arr * 100, 1) if all_arr > 0 else 0.0

    rows_html = ""
    for p in sorted_preds:
        rl_color = RISK_COLORS[p.risk_level]
        pct_bar = int(p.churn_score * 100)
        rows_html += f"""
        <tr style="border-bottom:1px solid #2d2d3f;">
          <td style="padding:10px 14px;font-weight:600;color:#e2e8f0;">{p.partner_id}</td>
          <td style="padding:10px 14px;min-width:200px;">
            <div style="background:#1e1e2e;border-radius:6px;height:20px;width:100%;overflow:hidden;">
              <div style="background:{rl_color};height:100%;width:{pct_bar}%;"></div>
            </div>
            <span style="font-size:11px;color:{rl_color};font-weight:700;">{p.churn_score:.2f} — {p.risk_level.upper()}</span>
          </td>
          <td style="padding:10px 14px;color:#94a3b8;">${p.arr_at_risk_usd:,.0f}</td>
          <td style="padding:10px 14px;color:#cbd5e1;font-size:12px;">{p.recommended_action}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Churn Predictor v2 — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background:#0f0f1a; color:#e2e8f0; font-family:'Segoe UI',system-ui,sans-serif; padding:24px; }}
    h1 {{ font-size:1.6rem; color:#c084fc; margin-bottom:4px; }}
    h2 {{ font-size:1.1rem; color:#a78bfa; margin:28px 0 12px; }}
    .subtitle {{ color:#64748b; font-size:0.875rem; margin-bottom:24px; }}
    .callout {{ background:#1e0a2e; border-left:4px solid #ef4444; border-radius:8px;
               padding:16px 20px; margin-bottom:28px; display:flex; gap:32px; flex-wrap:wrap; }}
    .callout-item {{ display:flex; flex-direction:column; }}
    .callout-value {{ font-size:1.8rem; font-weight:800; color:#ef4444; }}
    .callout-label {{ font-size:0.75rem; color:#94a3b8; margin-top:2px; }}
    table {{ width:100%; border-collapse:collapse; background:#13131f; border-radius:8px; overflow:hidden; margin-bottom:12px; }}
    th {{ background:#1e1e2e; text-align:left; padding:10px 14px; font-size:12px; color:#94a3b8; text-transform:uppercase; }}
    tr:hover td {{ background:#1a1a2e; }}
  </style>
</head>
<body>
  <h1>Customer Churn Predictor v2</h1>
  <p class="subtitle">OCI Robot Cloud · Design Partner Risk Dashboard · Port 8082</p>
  <div class="callout">
    <div class="callout-item"><span class="callout-value">${total_arr:,.0f}</span><span class="callout-label">ARR at Risk (medium/high/critical)</span></div>
    <div class="callout-item"><span class="callout-value">{pct}%</span><span class="callout-label">of Total Pipeline ARR</span></div>
    <div class="callout-item"><span class="callout-value">${all_arr:,.0f}</span><span class="callout-label">Total Pipeline ARR</span></div>
    <div class="callout-item"><span class="callout-value">{len(sorted_preds)}</span><span class="callout-label">Active Partners Monitored</span></div>
  </div>
  <h2>Risk Overview</h2>
  <table>
    <thead><tr><th>Partner</th><th>Churn Score</th><th>ARR at Risk</th><th>Recommended Action</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return build_dashboard()


@app.get("/api/predictions", response_model=List[ChurnPrediction])
async def get_all_predictions():
    return sorted(_predictions.values(), key=lambda p: p.churn_score, reverse=True)


@app.get("/api/predictions/{partner_id}", response_model=ChurnPrediction)
async def get_prediction(partner_id: str):
    pred = _predictions.get(partner_id)
    if pred is None:
        raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found.")
    return pred


@app.post("/api/refresh", response_model=List[ChurnPrediction])
async def refresh_predictions():
    _refresh_all()
    return sorted(_predictions.values(), key=lambda p: p.churn_score, reverse=True)


@app.get("/api/summary", response_model=SummaryResponse)
async def get_summary():
    preds = list(_predictions.values())
    at_risk_levels = {"medium", "high", "critical"}
    total_at_risk = sum(p.arr_at_risk_usd for p in preds if p.risk_level in at_risk_levels)
    total_pipeline = sum(p.arr_at_risk_usd for p in preds)
    count_by_level: dict = {}
    for p in preds:
        count_by_level[p.risk_level] = count_by_level.get(p.risk_level, 0) + 1
    avg_score = round(sum(p.churn_score for p in preds) / len(preds), 4) if preds else 0.0
    return SummaryResponse(
        total_arr_at_risk_usd=round(total_at_risk, 2),
        total_pipeline_arr_usd=round(total_pipeline, 2),
        pct_pipeline_at_risk=round(total_at_risk / total_pipeline * 100, 1) if total_pipeline else 0.0,
        count_by_risk_level=count_by_level,
        avg_churn_score=avg_score,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "customer_churn_predictor_v2", "port": 8082}


if __name__ == "__main__":
    uvicorn.run("customer_churn_predictor_v2:app", host="0.0.0.0", port=8082, reload=True)
