#!/usr/bin/env python3
"""
OCI Robot Cloud — Model Registry API
FastAPI service on port 8076 for tracking GR00T N1.6 fine-tuned models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ModelEntry(BaseModel):
    id: str
    name: str
    version: str
    base_model: str = "nvidia/GR00T-N1.6-3B"
    task: str
    training_run_id: Optional[str] = None
    mae: Optional[float] = None
    success_rate: Optional[float] = None
    latency_ms: Optional[float] = None
    created_at: str
    status: str  # active | archived | staging
    checkpoint_path: Optional[str] = None
    training_steps: Optional[int] = None
    notes: Optional[str] = None


class RegisterRequest(BaseModel):
    name: str
    version: str
    base_model: str = "nvidia/GR00T-N1.6-3B"
    task: str
    training_run_id: Optional[str] = None
    mae: Optional[float] = None
    success_rate: Optional[float] = None
    latency_ms: Optional[float] = None
    status: str = "staging"
    checkpoint_path: Optional[str] = None
    training_steps: Optional[int] = None
    notes: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(active|archived|staging)$")
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# In-memory registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, ModelEntry] = {}


def _ts(date_str: str) -> str:
    """Return an ISO-8601 timestamp string from a simple date string."""
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).isoformat()


def _seed_registry() -> None:
    seed_data = [
        ModelEntry(
            id="groot-baseline-v1-0",
            name="groot_baseline_v1.0",
            version="1.0",
            task="pick_cube",
            training_run_id="run-bc-001",
            mae=0.103,
            success_rate=0.05,
            latency_ms=227.0,
            created_at=_ts("2026-01-10"),
            status="archived",
            checkpoint_path="/mnt/checkpoints/groot_baseline_v1.0/final",
            training_steps=2000,
            notes="Baseline BC policy; 200 demos, no SDG.",
        ),
        ModelEntry(
            id="groot-sdg-v1-1",
            name="groot_sdg_v1.1",
            version="1.1",
            task="pick_cube",
            training_run_id="run-sdg-002",
            mae=0.048,
            success_rate=0.22,
            latency_ms=227.0,
            created_at=_ts("2026-01-18"),
            status="archived",
            checkpoint_path="/mnt/checkpoints/groot_sdg_v1.1/final",
            training_steps=5000,
            notes="Genesis SDG augmentation; 1000 demos. 2.5x MAE improvement.",
        ),
        ModelEntry(
            id="groot-ik-v1-2",
            name="groot_ik_v1.2",
            version="1.2",
            task="pick_cube",
            training_run_id="run-sdg-ik-003",
            mae=0.021,
            success_rate=0.41,
            latency_ms=227.0,
            created_at=_ts("2026-02-01"),
            status="archived",
            checkpoint_path="/mnt/checkpoints/groot_ik_v1.2/final",
            training_steps=10000,
            notes="IK motion-planned SDG; 8.7x MAE vs baseline. MAE 0.013 on IK subset.",
        ),
        ModelEntry(
            id="groot-dagger-v1-5",
            name="groot_dagger_v1.5",
            version="1.5",
            task="pick_cube",
            training_run_id="run-dagger-005",
            mae=0.016,
            success_rate=0.05,
            latency_ms=231.0,
            created_at=_ts("2026-02-14"),
            status="staging",
            checkpoint_path="/mnt/checkpoints/groot_dagger_v1.5/step_5000",
            training_steps=5000,
            notes="DAgger run5; 5000 steps on 99 episodes — insufficient data vs 1000-demo BC. Needs 1000+ DAgger eps.",
        ),
        ModelEntry(
            id="groot-multitask-v2-0",
            name="groot_multitask_v2.0",
            version="2.0",
            task="multi_task",
            training_run_id="run-mt-010",
            mae=0.019,
            success_rate=0.68,
            latency_ms=241.0,
            created_at=_ts("2026-02-28"),
            status="active",
            checkpoint_path="/mnt/checkpoints/groot_multitask_v2.0/final",
            training_steps=20000,
            notes="Multi-task policy: pick_cube + stack_blocks + push_T. Curriculum SDG training.",
        ),
        ModelEntry(
            id="groot-continual-v2-1",
            name="groot_continual_v2.1",
            version="2.1",
            task="multi_task",
            training_run_id="run-cl-011",
            mae=0.017,
            success_rate=0.71,
            latency_ms=243.0,
            created_at=_ts("2026-03-10"),
            status="active",
            checkpoint_path="/mnt/checkpoints/groot_continual_v2.1/final",
            training_steps=25000,
            notes="Continual learning on top of v2.0; auto-retrain trigger at SR < 0.60. Best overall model.",
        ),
        ModelEntry(
            id="groot-distilled-v2-2",
            name="groot_distilled_v2.2",
            version="2.2",
            task="pick_cube",
            training_run_id="run-distill-012",
            mae=0.018,
            success_rate=0.69,
            latency_ms=156.0,
            created_at=_ts("2026-03-18"),
            status="active",
            checkpoint_path="/mnt/checkpoints/groot_distilled_v2.2/final",
            training_steps=15000,
            notes="Policy distillation from v2.1; 1B-param student. 35% latency reduction, <1pp SR drop. Jetson-deployable.",
        ),
        ModelEntry(
            id="groot-lora-v2-3",
            name="groot_lora_v2.3",
            version="2.3",
            task="stack_blocks",
            training_run_id="run-lora-013",
            mae=0.022,
            success_rate=0.62,
            latency_ms=229.0,
            created_at=_ts("2026-03-25"),
            status="staging",
            checkpoint_path="/mnt/checkpoints/groot_lora_v2.3/step_8000",
            training_steps=8000,
            notes="LoRA fine-tune (rank=16) on stack_blocks task. In staging — eval suite running.",
        ),
    ]
    for entry in seed_data:
        _REGISTRY[entry.id] = entry


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OCI Robot Cloud — Model Registry",
    description="GR00T N1.6 fine-tuned model registry for OCI Robot Cloud.",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event() -> None:
    _seed_registry()


# ---------------------------------------------------------------------------
# HTML dashboard helpers
# ---------------------------------------------------------------------------

_STATUS_BADGE = {
    "active":   ('<span style="background:#16a34a;color:#fff;padding:2px 10px;'
                 'border-radius:12px;font-size:12px;font-weight:600;">active</span>'),
    "staging":  ('<span style="background:#d97706;color:#fff;padding:2px 10px;'
                 'border-radius:12px;font-size:12px;font-weight:600;">staging</span>'),
    "archived": ('<span style="background:#4b5563;color:#d1d5db;padding:2px 10px;'
                 'border-radius:12px;font-size:12px;font-weight:600;">archived</span>'),
}


def _fmt(val, fmt="{:.4f}", fallback="\u2014"):
    if val is None:
        return fallback
    return fmt.format(val)


def _build_dashboard() -> str:
    models = list(_REGISTRY.values())
    total = len(models)
    active_count = sum(1 for m in models if m.status == "active")
    best_sr = max((m.success_rate for m in models if m.success_rate is not None), default=None)
    best_mae = min((m.mae for m in models if m.mae is not None), default=None)

    rows = ""
    for m in sorted(models, key=lambda x: x.created_at, reverse=True):
        badge = _STATUS_BADGE.get(m.status, m.status)
        rows += f"""
        <tr>
          <td><code style="color:#93c5fd">{m.id}</code></td>
          <td>{m.name}</td>
          <td>{m.version}</td>
          <td>{m.task}</td>
          <td>{_fmt(m.mae)}</td>
          <td>{_fmt(m.success_rate, "{:.1%}")}</td>
          <td>{_fmt(m.latency_ms, "{:.0f} ms")}</td>
          <td>{m.training_steps if m.training_steps else "\u2014"}</td>
          <td>{badge}</td>
          <td style="color:#9ca3af;font-size:12px">{m.created_at[:10]}</td>
          <td style="color:#9ca3af;font-size:12px;max-width:260px">{m.notes or ""}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud \u2014 Model Registry</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 24px;
      background: #0f172a; color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px;
    }}
    h1 {{ color: #76ef80; margin: 0 0 4px; font-size: 22px; letter-spacing: .5px; }}
    .subtitle {{ color: #64748b; margin: 0 0 20px; font-size: 13px; }}
    .stats {{
      display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap;
    }}
    .stat {{
      background: #1e293b; border: 1px solid #334155;
      border-radius: 8px; padding: 12px 20px; min-width: 140px;
    }}
    .stat-label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .8px; }}
    .stat-value {{ color: #f1f5f9; font-size: 24px; font-weight: 700; margin-top: 4px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%; border-collapse: collapse; font-size: 13px;
    }}
    thead tr {{ background: #1e293b; }}
    th {{
      text-align: left; padding: 10px 12px; color: #94a3b8;
      font-size: 11px; text-transform: uppercase; letter-spacing: .6px;
      border-bottom: 1px solid #334155; white-space: nowrap;
    }}
    td {{
      padding: 10px 12px; border-bottom: 1px solid #1e293b;
      vertical-align: top;
    }}
    tr:hover td {{ background: #1e293b55; }}
    .footer {{ margin-top: 24px; color: #475569; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud \u2014 Model Registry</h1>
  <p class="subtitle">GR00T N1.6 fine-tuned policy models &nbsp;|&nbsp; Port 8076</p>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Total Models</div>
      <div class="stat-value">{total}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Active</div>
      <div class="stat-value" style="color:#4ade80">{active_count}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Best Success Rate</div>
      <div class="stat-value" style="color:#60a5fa">{f'{best_sr:.1%}' if best_sr is not None else '\u2014'}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Best MAE</div>
      <div class="stat-value" style="color:#f472b6">{f'{best_mae:.4f}' if best_mae is not None else '\u2014'}</div>
    </div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Ver</th>
          <th>Task</th>
          <th>MAE</th>
          <th>Success Rate</th>
          <th>Latency</th>
          <th>Steps</th>
          <th>Status</th>
          <th>Created</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <p class="footer">OCI Robot Cloud &mdash; Model Registry API &mdash; <a href="/docs" style="color:#64748b">OpenAPI docs</a></p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_build_dashboard())


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model_count": len(_REGISTRY)}


@app.get("/api/models", response_model=List[ModelEntry])
async def list_models(
    status: Optional[str] = None,
    task: Optional[str] = None,
) -> List[ModelEntry]:
    results = list(_REGISTRY.values())
    if status:
        results = [m for m in results if m.status == status]
    if task:
        results = [m for m in results if m.task == task]
    return sorted(results, key=lambda m: m.created_at, reverse=True)


@app.get("/api/models/compare")
async def compare_models(ids: str) -> dict:
    """Side-by-side comparison. Pass comma-separated model IDs."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 model IDs separated by commas.")
    missing = [i for i in id_list if i not in _REGISTRY]
    if missing:
        raise HTTPException(status_code=404, detail=f"Model(s) not found: {missing}")
    models = [_REGISTRY[i] for i in id_list]
    fields = ["name", "version", "task", "mae", "success_rate", "latency_ms",
              "training_steps", "status", "created_at", "notes"]
    comparison = {f: {m.id: getattr(m, f) for m in models} for f in fields}
    maes = {m.id: m.mae for m in models if m.mae is not None}
    srs = {m.id: m.success_rate for m in models if m.success_rate is not None}
    summary = {}
    if maes:
        summary["best_mae"] = min(maes, key=maes.__getitem__)
    if srs:
        summary["best_success_rate"] = max(srs, key=srs.__getitem__)
    return {"models": id_list, "comparison": comparison, "summary": summary}


@app.get("/api/models/{model_id}", response_model=ModelEntry)
async def get_model(model_id: str) -> ModelEntry:
    if model_id not in _REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return _REGISTRY[model_id]


@app.post("/api/models", response_model=ModelEntry, status_code=201)
async def register_model(req: RegisterRequest) -> ModelEntry:
    model_id = str(uuid.uuid4())[:8] + "-" + req.name.lower().replace(".", "-").replace("_", "-")
    now = datetime.now(timezone.utc).isoformat()
    entry = ModelEntry(
        id=model_id,
        name=req.name,
        version=req.version,
        base_model=req.base_model,
        task=req.task,
        training_run_id=req.training_run_id,
        mae=req.mae,
        success_rate=req.success_rate,
        latency_ms=req.latency_ms,
        created_at=now,
        status=req.status,
        checkpoint_path=req.checkpoint_path,
        training_steps=req.training_steps,
        notes=req.notes,
    )
    _REGISTRY[model_id] = entry
    return entry


@app.patch("/api/models/{model_id}/status", response_model=ModelEntry)
async def update_model_status(model_id: str, req: UpdateStatusRequest) -> ModelEntry:
    if model_id not in _REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    entry = _REGISTRY[model_id]
    updated = entry.model_copy(update={"status": req.status})
    if req.notes is not None:
        updated = updated.model_copy(update={"notes": req.notes})
    _REGISTRY[model_id] = updated
    return updated


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8076)
