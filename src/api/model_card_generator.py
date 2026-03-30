"""Model Card Generator — OCI Robot Cloud  (port 8200)

Auto-generates structured model cards for GR00T checkpoints.
Export formats: HTML, JSON, Markdown.
"""

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None  # type: ignore
    HTTPException = None  # type: ignore
    Query = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

import math
import json
from typing import Optional

# ---------------------------------------------------------------------------
# Static data store
# ---------------------------------------------------------------------------

MODEL_CARDS = {
    "oci-robot-cloud/groot-finetune-v2": {
        "model_id": "oci-robot-cloud/groot-finetune-v2",
        "base_model": "nvidia/GR00T-N1.6-3B",
        "task": "robot_manipulation — cube_lift (Franka Panda)",
        "training_data": "genesis_sdg_v3 (1600 curated demos) + dagger_run9 (1000 demos)",
        "training_compute": "2×A100_80GB, 5000 steps, 2.4h, $7.34",
        "metrics": {
            "success_rate": 0.78,
            "mae": 0.023,
            "latency_p50_ms": 226,
            "latency_p99_ms": 287,
        },
        "limitations": [
            "Only tested on cube_lift task",
            "Lighting variation reduces SR to 0.61",
            "Recovery behavior undertrained (21% recovery SR)",
        ],
        "intended_use": (
            "Fine-tuning demonstration for OCI Robot Cloud design partners; "
            "not production robot safety system"
        ),
        "version": "v1.0.1",
        "date": "2026-03-15",
        "license": "OCI Robot Cloud Commercial",
        "changelog": [
            {"version": "v1.0.1", "date": "2026-03-15", "note": "DAgger run9 data added; SR +0.03"},
            {"version": "v1.0.0", "date": "2026-02-28", "note": "Initial production release"},
        ],
    }
}

# ---------------------------------------------------------------------------
# SVG radar chart  (480 × 200)
# ---------------------------------------------------------------------------

def _radar_svg() -> str:
    """5-axis radar: SR / MAE_inv / Latency_inv / Robustness / Data_eff"""
    W, H, cx, cy, R = 480, 200, 180, 100, 80
    axes = ["Success\nRate", "MAE\nInv", "Latency\nInv", "Robustness", "Data\nEff"]
    model_vals  = [0.78, 0.77, 0.72, 0.61, 0.80]  # normalised 0‑1
    baseline_vals = [0.55, 0.60, 0.65, 0.50, 0.60]
    n = len(axes)

    def polar(val, idx, r_scale=1.0):
        angle = math.radians(-90 + idx * 360 / n)
        r = val * R * r_scale
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    # grid rings
    rings = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{polar(level,i)[0]:.1f},{polar(level,i)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'

    # spokes
    spokes = ""
    for i in range(n):
        x, y = polar(1.0, i)
        spokes += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#475569" stroke-width="1"/>\n'

    # baseline polygon
    b_pts = " ".join(f"{polar(v,i)[0]:.1f},{polar(v,i)[1]:.1f}" for i, v in enumerate(baseline_vals))
    # model polygon
    m_pts = " ".join(f"{polar(v,i)[0]:.1f},{polar(v,i)[1]:.1f}" for i, v in enumerate(model_vals))

    # axis labels
    label_offset = 14
    labels = ""
    for i, ax in enumerate(axes):
        lx, ly = polar(1.0, i)
        dx = lx - cx; dy = ly - cy
        mag = math.sqrt(dx*dx + dy*dy) or 1
        tx = lx + label_offset * dx / mag
        ty = ly + label_offset * dy / mag
        for j, line in enumerate(ax.split("\n")):
            labels += (f'<text x="{tx:.1f}" y="{ty + j*12:.1f}" '
                       f'text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{line}</text>\n')

    # legend (right side)
    legend = (
        f'<rect x="310" y="60" width="10" height="10" fill="#C74634" opacity="0.7"/>'
        f'<text x="325" y="69" fill="#94a3b8" font-size="10" font-family="monospace">groot-finetune-v2</text>'
        f'<rect x="310" y="80" width="10" height="10" fill="#475569" opacity="0.7"/>'
        f'<text x="325" y="89" fill="#94a3b8" font-size="10" font-family="monospace">Baseline</text>'
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
{rings}{spokes}
<polygon points="{b_pts}" fill="#475569" fill-opacity="0.4" stroke="#64748b" stroke-width="1.5"/>
<polygon points="{m_pts}" fill="#C74634" fill-opacity="0.45" stroke="#C74634" stroke-width="2"/>
{labels}{legend}
<text x="{cx}" y="{H-6}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Radar: normalised 0‑1 per axis</text>
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# Format renderers
# ---------------------------------------------------------------------------

def _card_to_markdown(card: dict) -> str:
    m = card["metrics"]
    lims = "\n".join(f"- {l}" for l in card["limitations"])
    changelog = "\n".join(
        f"| {c['version']} | {c['date']} | {c['note']} |" for c in card["changelog"]
    )
    return f"""# Model Card — {card['model_id']}

> **Version:** {card['version']} | **Date:** {card['date']} | **License:** {card['license']}

## Overview
| Field | Value |
|-------|-------|
| Base Model | `{card['base_model']}` |
| Task | {card['task']} |
| Training Data | {card['training_data']} |
| Compute | {card['training_compute']} |

## Metrics
| Metric | Value |
|--------|-------|
| Success Rate | {m['success_rate']} |
| MAE | {m['mae']} |
| Latency p50 | {m['latency_p50_ms']} ms |
| Latency p99 | {m['latency_p99_ms']} ms |

## Limitations
{lims}

## Intended Use
{card['intended_use']}

## Usage
```python
from oci_robot_cloud import RobotCloudClient
client = RobotCloudClient(model_id="{card['model_id']}")
result = client.predict(observation=obs, action_horizon=16)
```

## Changelog
| Version | Date | Note |
|---------|------|------|
{changelog}
"""


def _card_to_html(card: dict) -> str:
    m = card["metrics"]
    radar = _radar_svg()
    lims_html = "".join(f"<li>{l}</li>" for l in card["limitations"])
    changelog_rows = "".join(
        f"<tr><td>{c['version']}</td><td>{c['date']}</td><td>{c['note']}</td></tr>"
        for c in card["changelog"]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Model Card — {card['model_id']}</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;line-height:1.6}}
  h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}
  h2{{color:#C74634;font-size:1rem;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid #1e293b;padding-bottom:4px;margin-top:28px}}
  .meta{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
  table{{border-collapse:collapse;width:100%;margin-bottom:8px}}
  th,td{{padding:6px 10px;border:1px solid #1e293b;font-size:.88rem}}
  th{{background:#1e293b;color:#94a3b8;text-align:left}}
  td{{color:#cbd5e1}}
  .best{{color:#38bdf8;font-weight:700}}
  pre{{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:14px;font-size:.82rem;overflow-x:auto;color:#38bdf8}}
  ul{{color:#94a3b8;padding-left:20px}}
  .badge{{display:inline-block;background:#C74634;color:#fff;font-size:.75rem;padding:2px 8px;border-radius:4px;margin-left:8px}}
  .card-wrap{{max-width:860px;margin:0 auto}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
  .radar-wrap{{margin:16px 0}}
</style>
</head>
<body>
<div class="card-wrap">
  <h1>Model Card <span class="badge">{card['version']}</span></h1>
  <div class="meta">{card['model_id']} &nbsp;|&nbsp; {card['date']} &nbsp;|&nbsp; {card['license']}</div>

  <h2>Overview</h2>
  <table>
    <tr><th>Field</th><th>Value</th></tr>
    <tr><td>Base Model</td><td><code>{card['base_model']}</code></td></tr>
    <tr><td>Task</td><td>{card['task']}</td></tr>
    <tr><td>Training Data</td><td>{card['training_data']}</td></tr>
    <tr><td>Compute</td><td>{card['training_compute']}</td></tr>
  </table>

  <h2>Metrics</h2>
  <div class="grid2">
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Success Rate</td><td class="best">{m['success_rate']}</td></tr>
      <tr><td>MAE</td><td>{m['mae']}</td></tr>
      <tr><td>Latency p50</td><td>{m['latency_p50_ms']} ms</td></tr>
      <tr><td>Latency p99</td><td>{m['latency_p99_ms']} ms</td></tr>
    </table>
    <div class="radar-wrap">{radar}</div>
  </div>

  <h2>Training</h2>
  <table>
    <tr><th>Field</th><th>Value</th></tr>
    <tr><td>Data</td><td>{card['training_data']}</td></tr>
    <tr><td>Compute</td><td>{card['training_compute']}</td></tr>
  </table>

  <h2>Limitations</h2>
  <ul>{lims_html}</ul>

  <h2>Intended Use</h2>
  <p style="color:#94a3b8">{card['intended_use']}</p>

  <h2>Usage</h2>
  <pre>from oci_robot_cloud import RobotCloudClient
client = RobotCloudClient(model_id="{card['model_id']}")
result = client.predict(observation=obs, action_horizon=16)
print(result.actions)  # shape: (16, 7) — joint angles</pre>

  <h2>Changelog</h2>
  <table>
    <tr><th>Version</th><th>Date</th><th>Note</th></tr>
    {changelog_rows}
  </table>
</div>
</body></html>"""


def _compare_html(card_a: dict, card_b: dict) -> str:
    ma, mb = card_a["metrics"], card_b["metrics"]

    def cell(a, b, key, fmt="{}"):
        va, vb = a[key], b[key]
        color_a = "#38bdf8" if va >= vb else "#e2e8f0"
        color_b = "#38bdf8" if vb >= va else "#e2e8f0"
        # For MAE lower is better
        if "mae" in key:
            color_a = "#38bdf8" if va <= vb else "#e2e8f0"
            color_b = "#38bdf8" if vb <= va else "#e2e8f0"
        return (
            f'<td style="color:{color_a}">{fmt.format(va)}</td>'
            f'<td style="color:{color_b}">{fmt.format(vb)}</td>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Compare Models</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;font-size:1.3rem}}
  table{{border-collapse:collapse;width:100%}}
  th,td{{padding:8px 12px;border:1px solid #1e293b;font-size:.88rem}}
  th{{background:#1e293b;color:#94a3b8}}
</style></head>
<body>
<h1>Model Comparison</h1>
<table>
  <tr><th>Metric</th><th>{card_a['model_id']}</th><th>{card_b['model_id']}</th></tr>
  <tr><td>Success Rate</td>{cell(ma,mb,'success_rate')}</tr>
  <tr><td>MAE</td>{cell(ma,mb,'mae')}</tr>
  <tr><td>Latency p50 (ms)</td>{cell(ma,mb,'latency_p50_ms')}</tr>
  <tr><td>Latency p99 (ms)</td>{cell(ma,mb,'latency_p99_ms')}</tr>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    cards_html = ""
    for mid, card in MODEL_CARDS.items():
        sr = card["metrics"]["success_rate"]
        bar_w = int(sr * 180)
        cards_html += f"""<div class="card-item">
  <div class="card-title">{mid}</div>
  <div class="card-meta">{card['task']}</div>
  <div class="sr-bar"><div class="sr-fill" style="width:{bar_w}px"></div></div>
  <div class="card-meta" style="margin-top:4px">SR: <span style="color:#38bdf8">{sr}</span> &nbsp; MAE: {card['metrics']['mae']} &nbsp; v{card['version']}</div>
  <div style="margin-top:8px">
    <a href="/card/{mid}?format=html" class="btn">HTML</a>
    <a href="/card/{mid}?format=json" class="btn">JSON</a>
    <a href="/card/{mid}?format=markdown" class="btn">MD</a>
  </div>
</div>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Model Card Generator — OCI Robot Cloud</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;margin-bottom:4px}}h2{{color:#C74634;font-size:1rem}}
  .subtitle{{color:#64748b;font-size:.9rem;margin-bottom:28px}}
  .card-item{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:18px;max-width:520px;margin-bottom:16px}}
  .card-title{{color:#38bdf8;font-size:1rem;font-weight:600}}
  .card-meta{{color:#94a3b8;font-size:.83rem;margin-top:4px}}
  .sr-bar{{background:#334155;height:8px;border-radius:4px;width:180px;margin-top:8px}}
  .sr-fill{{background:#C74634;height:8px;border-radius:4px}}
  .btn{{display:inline-block;background:#C74634;color:#fff;text-decoration:none;font-size:.78rem;padding:3px 10px;border-radius:4px;margin-right:6px}}
  .ep{{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:12px;font-size:.82rem;color:#64748b;margin-top:24px}}
</style></head>
<body>
<h1>Model Card Generator</h1>
<div class="subtitle">OCI Robot Cloud · Port 8200 · Auto-generates structured model cards for GR00T checkpoints</div>
<h2>Registered Models</h2>
{cards_html}
<div class="ep">
  <b style="color:#94a3b8">Endpoints</b><br>
  GET /card/{{model_id}}?format=html|json|markdown<br>
  GET /cards — list all<br>
  GET /compare/{{id1}}/{{id2}} — side-by-side
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="Model Card Generator",
        description="Auto-generates model cards for GR00T checkpoints",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/cards")
    def list_cards():
        return [
            {
                "model_id": mid,
                "version": c["version"],
                "date": c["date"],
                "success_rate": c["metrics"]["success_rate"],
            }
            for mid, c in MODEL_CARDS.items()
        ]

    @app.get("/card/{model_id:path}")
    def get_card(model_id: str, format: str = Query("html", enum=["html", "json", "markdown"])):
        # Support URL-encoded slash in model_id
        if model_id not in MODEL_CARDS:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
        card = MODEL_CARDS[model_id]
        if format == "json":
            return JSONResponse(content=card)
        if format == "markdown":
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(_card_to_markdown(card))
        return HTMLResponse(_card_to_html(card))

    @app.get("/compare/{id1:path}")
    def compare(id1: str, id2: str = Query(...)):
        if id1 not in MODEL_CARDS:
            raise HTTPException(status_code=404, detail=f"Model '{id1}' not found")
        if id2 not in MODEL_CARDS:
            raise HTTPException(status_code=404, detail=f"Model '{id2}' not found")
        return HTMLResponse(_compare_html(MODEL_CARDS[id1], MODEL_CARDS[id2]))


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — pip install uvicorn fastapi")
    uvicorn.run("model_card_generator:app", host="0.0.0.0", port=8200, reload=False)
