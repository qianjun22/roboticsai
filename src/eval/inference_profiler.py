"""OCI Robot Cloud — Deep Inference Pipeline Profiler
Port 8144 | FastAPI service with flame-graph style visualization
"""
from __future__ import annotations

import math
import json
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
PIPELINE_STAGES: list[dict[str, Any]] = [
    {
        "name": "image_capture",
        "total_ms": 8.2,
        "color": "#22c55e",
        "ops": [
            {"name": "frame_grab", "ms": 5.1},
            {"name": "resize_224", "ms": 1.8},
            {"name": "normalize", "ms": 1.3},
        ],
    },
    {
        "name": "tokenize",
        "total_ms": 12.4,
        "color": "#06b6d4",
        "ops": [
            {"name": "text_encode", "ms": 6.2},
            {"name": "pad_sequence", "ms": 4.1},
            {"name": "to_tensor", "ms": 2.1},
        ],
    },
    {
        "name": "vit_encoder",
        "total_ms": 48.7,
        "color": "#38bdf8",
        "ops": [
            {"name": "patch_embed", "ms": 3.2},
            {"name": "attn_blocks_12x", "ms": 38.4},
            {"name": "pool_proj", "ms": 7.1},
        ],
    },
    {
        "name": "llm_backbone",
        "total_ms": 142.3,
        "color": "#f97316",
        "ops": [
            {"name": "embed_lookup", "ms": 4.1},
            {"name": "transformer_24x", "ms": 121.8},
            {"name": "lm_head", "ms": 16.4},
        ],
    },
    {
        "name": "action_decoder",
        "total_ms": 9.8,
        "color": "#C74634",
        "ops": [
            {"name": "decode_chunks", "ms": 5.4},
            {"name": "smooth_traj", "ms": 2.8},
            {"name": "clamp_joints", "ms": 1.6},
        ],
    },
    {
        "name": "send_to_robot",
        "total_ms": 4.6,
        "color": "#94a3b8",
        "ops": [
            {"name": "serialize", "ms": 0.8},
            {"name": "zmq_send", "ms": 3.8},
        ],
    },
]

TOTAL_P50_MS = 226.0
SLA_TARGET_MS = 300.0
HEADROOM_MS = SLA_TARGET_MS - TOTAL_P50_MS

RECOMMENDATIONS = [
    {
        "target": "llm_backbone",
        "current_ms": 142.3,
        "technique": "FP8 quantization",
        "est_reduction_pct": 30,
        "projected_ms": 99.0,
    },
    {
        "target": "vit_encoder",
        "current_ms": 48.7,
        "technique": "TensorRT optimization",
        "est_reduction_pct": 20,
        "projected_ms": 39.0,
    },
]
PROJECTED_TOTAL_MS = 180.0


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------
def _darken(hex_color: str, factor: float = 0.75) -> str:
    """Return a slightly darker version of a hex color."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r2, g2, b2 = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r2:02x}{g2:02x}{b2:02x}"


def _build_flame_svg() -> str:
    """680x280 flame-graph style SVG."""
    W, H = 680, 280
    LABEL_W = 120
    CHART_W = W - LABEL_W - 20
    BAR_H = 28
    BAR_GAP = 16
    TOP_PAD = 20
    AXIS_H = 24

    total_ms = TOTAL_P50_MS
    scale = CHART_W / total_ms  # px per ms

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )
    # Title
    lines.append(
        f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Inference Flame Graph (p50={total_ms}ms)</text>'
    )

    # Axis ticks
    tick_intervals = [0, 50, 100, 150, 200, 226]
    for tick in tick_intervals:
        x = LABEL_W + tick * scale
        lines.append(
            f'<line x1="{x:.1f}" y1="{TOP_PAD+5}" x2="{x:.1f}" '
            f'y2="{H - AXIS_H}" stroke="#334155" stroke-width="0.5" stroke-dasharray="3,3"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="{H - 6}" fill="#64748b" font-size="9" text-anchor="middle">{tick}ms</text>'
        )

    # Bars
    x_cursor = 0.0
    for i, stage in enumerate(PIPELINE_STAGES):
        y = TOP_PAD + 10 + i * (BAR_H + BAR_GAP)
        base_color = stage["color"]
        x_start = LABEL_W + x_cursor * scale
        bar_w = stage["total_ms"] * scale

        # Full stage background bar
        lines.append(
            f'<rect x="{x_start:.1f}" y="{y}" width="{bar_w:.1f}" height="{BAR_H}" '
            f'fill="{base_color}" rx="2" opacity="0.3"/>'
        )

        # Sub-operation segments
        sub_x = x_start
        for j, op in enumerate(stage["ops"]):
            seg_w = op["ms"] * scale
            shade = _darken(base_color, 0.6 + 0.2 * (j % 2))
            lines.append(
                f'<rect x="{sub_x:.1f}" y="{y+4}" width="{max(seg_w-1,1):.1f}" height="{BAR_H-8}" '
                f'fill="{shade}" rx="1"/>'
            )
            # Sub-op label if wide enough
            if seg_w > 40:
                lines.append(
                    f'<text x="{sub_x + seg_w/2:.1f}" y="{y + BAR_H//2 + 3}" '
                    f'fill="#f1f5f9" font-size="8" text-anchor="middle">{op["name"]}</text>'
                )
            sub_x += seg_w

        # Stage label
        lines.append(
            f'<text x="{LABEL_W - 4}" y="{y + BAR_H//2 + 4}" fill="{base_color}" '
            f'font-size="9" text-anchor="end" font-weight="bold">{stage["name"]}</text>'
        )
        # ms label
        lines.append(
            f'<text x="{x_start + bar_w + 3}" y="{y + BAR_H//2 + 4}" fill="#94a3b8" '
            f'font-size="8">{stage["total_ms"]}ms</text>'
        )

        x_cursor += stage["total_ms"]

    lines.append("</svg>")
    return "\n".join(lines)


def _build_donut_svg() -> str:
    """480x300 donut chart SVG for stage breakdown."""
    W, H = 480, 300
    CX, CY, R_OUT, R_IN = 180, 150, 120, 65

    total = sum(s["total_ms"] for s in PIPELINE_STAGES)
    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )
    lines.append(
        f'<text x="{CX}" y="22" fill="#e2e8f0" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Stage Breakdown</text>'
    )

    angle = -math.pi / 2  # start at top
    for stage in PIPELINE_STAGES:
        sweep = 2 * math.pi * stage["total_ms"] / total
        x1_o = CX + R_OUT * math.cos(angle)
        y1_o = CY + R_OUT * math.sin(angle)
        x1_i = CX + R_IN * math.cos(angle)
        y1_i = CY + R_IN * math.sin(angle)
        mid_a = angle + sweep / 2
        angle += sweep
        x2_o = CX + R_OUT * math.cos(angle)
        y2_o = CY + R_OUT * math.sin(angle)
        x2_i = CX + R_IN * math.cos(angle)
        y2_i = CY + R_IN * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        d = (
            f"M {x1_i:.2f} {y1_i:.2f} "
            f"L {x1_o:.2f} {y1_o:.2f} "
            f"A {R_OUT} {R_OUT} 0 {large} 1 {x2_o:.2f} {y2_o:.2f} "
            f"L {x2_i:.2f} {y2_i:.2f} "
            f"A {R_IN} {R_IN} 0 {large} 0 {x1_i:.2f} {y1_i:.2f} Z"
        )
        lines.append(f'<path d="{d}" fill="{stage["color"]}" stroke="#0f172a" stroke-width="1.5"/>')

        # Percent label
        pct = stage["total_ms"] / total * 100
        lx = CX + (R_IN + (R_OUT - R_IN) / 2) * math.cos(mid_a)
        ly = CY + (R_IN + (R_OUT - R_IN) / 2) * math.sin(mid_a)
        if pct > 6:
            lines.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#0f172a" font-size="8" '
                f'text-anchor="middle" font-weight="bold">{pct:.0f}%</text>'
            )

    # Centre label
    lines.append(
        f'<text x="{CX}" y="{CY-6}" fill="#e2e8f0" font-size="14" '
        f'text-anchor="middle" font-weight="bold">226ms</text>'
    )
    lines.append(
        f'<text x="{CX}" y="{CY+12}" fill="#94a3b8" font-size="9" text-anchor="middle">p50 total</text>'
    )

    # Legend
    lx0, ly0 = 320, 60
    for i, stage in enumerate(PIPELINE_STAGES):
        ly = ly0 + i * 34
        lines.append(f'<rect x="{lx0}" y="{ly}" width="12" height="12" fill="{stage["color"]}" rx="2"/>')
        lines.append(
            f'<text x="{lx0+16}" y="{ly+10}" fill="#e2e8f0" font-size="10">{stage["name"]}</text>'
        )
        lines.append(
            f'<text x="{lx0+16}" y="{ly+22}" fill="#64748b" font-size="9">{stage["total_ms"]}ms '
            f'({stage["total_ms"]/total*100:.0f}%)</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', monospace; }
.header { background: #1e293b; border-bottom: 2px solid #C74634;
          padding: 14px 28px; display: flex; align-items: center; gap: 16px; }
.header h1 { font-size: 18px; color: #f1f5f9; }
.header .badge { background: #C74634; color: #fff; padding: 2px 10px;
                 border-radius: 999px; font-size: 11px; font-weight: bold; }
.main { padding: 24px 28px; }
.cards { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin-bottom: 24px; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 10px;
        padding: 16px 18px; }
.card .label { color: #64748b; font-size: 11px; text-transform: uppercase;
               letter-spacing: .08em; margin-bottom: 6px; }
.card .value { font-size: 26px; font-weight: 700; color: #38bdf8; }
.card .sub { color: #94a3b8; font-size: 11px; margin-top: 4px; }
.card.warn .value { color: #f97316; }
.card.good .value { color: #22c55e; }
.section { background: #1e293b; border: 1px solid #334155; border-radius: 10px;
           padding: 18px 20px; margin-bottom: 20px; }
.section h2 { font-size: 14px; color: #38bdf8; margin-bottom: 14px;
              border-bottom: 1px solid #334155; padding-bottom: 8px; }
.recs { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 8px; }
.rec-card { background: #0f172a; border: 1px solid #334155; border-radius: 8px;
            padding: 14px 16px; }
.rec-card .rtitle { color: #f97316; font-size: 13px; font-weight: 600;
                    margin-bottom: 6px; }
.rec-card .rrow { display: flex; justify-content: space-between;
                  font-size: 11px; color: #94a3b8; margin-top: 4px; }
.rec-card .rrow span { color: #e2e8f0; }
.tag { display: inline-block; background: #172554; color: #38bdf8;
       border: 1px solid #1d4ed8; border-radius: 4px; font-size: 10px;
       padding: 2px 8px; margin-top: 6px; }
.projected { background: #0f172a; border: 1px solid #22c55e; border-radius: 8px;
             padding: 12px 16px; margin-top: 14px; color: #22c55e;
             font-size: 13px; text-align: center; font-weight: 600; }
"""


def _build_dashboard_html() -> str:
    flame_svg = _build_flame_svg()
    donut_svg = _build_donut_svg()

    bottleneck = max(PIPELINE_STAGES, key=lambda s: s["total_ms"])

    recs_html = ""
    for r in RECOMMENDATIONS:
        recs_html += f"""
        <div class="rec-card">
          <div class="rtitle">{r['target']}</div>
          <div class="rrow">Current latency: <span>{r['current_ms']}ms</span></div>
          <div class="rrow">Technique: <span>{r['technique']}</span></div>
          <div class="rrow">Est. reduction: <span>{r['est_reduction_pct']}%</span></div>
          <div class="rrow">Projected: <span>{r['projected_ms']}ms</span></div>
          <div class="tag">{r['technique']}</div>
        </div>"""

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Inference Profiler — Port 8144</title>
<style>{CSS}</style></head><body>
<div class="header">
  <span style="font-size:22px">&#128269;</span>
  <h1>Inference Pipeline Profiler</h1>
  <span class="badge">PORT 8144</span>
  <span style="margin-left:auto;color:#64748b;font-size:12px">OCI Robot Cloud · groot_finetune_v2</span>
</div>
<div class="main">
  <div class="cards">
    <div class="card">
      <div class="label">Total p50 Latency</div>
      <div class="value">{TOTAL_P50_MS}ms</div>
      <div class="sub">end-to-end inference</div>
    </div>
    <div class="card good">
      <div class="label">SLA Target</div>
      <div class="value">&lt;{SLA_TARGET_MS:.0f}ms</div>
      <div class="sub">within budget</div>
    </div>
    <div class="card good">
      <div class="label">Headroom</div>
      <div class="value">{HEADROOM_MS:.0f}ms</div>
      <div class="sub">before SLA breach</div>
    </div>
    <div class="card warn">
      <div class="label">Bottleneck</div>
      <div class="value" style="font-size:16px">{bottleneck['name']}</div>
      <div class="sub">{bottleneck['total_ms']}ms · {bottleneck['total_ms']/TOTAL_P50_MS*100:.0f}% of total</div>
    </div>
  </div>

  <div class="section">
    <h2>Flame Graph — Pipeline Stages</h2>
    {flame_svg}
  </div>

  <div class="section">
    <h2>Stage Breakdown</h2>
    {donut_svg}
  </div>

  <div class="section">
    <h2>Optimization Opportunities</h2>
    <div class="recs">{recs_html}</div>
    <div class="projected">
      Projected total after optimizations: ~{PROJECTED_TOTAL_MS}ms
      &nbsp;&#8594;&nbsp; {(TOTAL_P50_MS - PROJECTED_TOTAL_MS)/TOTAL_P50_MS*100:.0f}% improvement
    </div>
  </div>
</div></body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(title="OCI Inference Profiler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_build_dashboard_html())

    @app.get("/stages")
    async def stages() -> JSONResponse:
        return JSONResponse(content={"stages": PIPELINE_STAGES, "total_p50_ms": TOTAL_P50_MS})

    @app.get("/summary")
    async def summary() -> JSONResponse:
        bottleneck = max(PIPELINE_STAGES, key=lambda s: s["total_ms"])
        return JSONResponse(content={
            "total_p50_ms": TOTAL_P50_MS,
            "sla_target_ms": SLA_TARGET_MS,
            "headroom_ms": HEADROOM_MS,
            "bottleneck": {"stage": bottleneck["name"], "ms": bottleneck["total_ms"]},
            "projected_optimized_ms": PROJECTED_TOTAL_MS,
        })

    @app.get("/recommendations")
    async def recommendations() -> JSONResponse:
        return JSONResponse(content={
            "recommendations": RECOMMENDATIONS,
            "projected_total_ms": PROJECTED_TOTAL_MS,
            "improvement_pct": round((TOTAL_P50_MS - PROJECTED_TOTAL_MS) / TOTAL_P50_MS * 100, 1),
        })


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("inference_profiler:app", host="0.0.0.0", port=8144, reload=True)
