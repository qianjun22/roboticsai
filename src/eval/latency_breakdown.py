"""Latency Breakdown Waterfall — OCI Robot Cloud  (port 8188)"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

STAGES = [
    "network_in", "auth", "deserialize", "preprocess",
    "tokenize", "vit_encode", "llm_forward",
    "action_decode", "serialize", "network_out",
]

STAGE_COLORS = [
    "#38bdf8",  # network_in  — sky blue
    "#818cf8",  # auth        — indigo
    "#34d399",  # deserialize — emerald
    "#fbbf24",  # preprocess  — amber
    "#f472b6",  # tokenize    — pink
    "#a78bfa",  # vit_encode  — violet
    "#C74634",  # llm_forward — oracle red
    "#fb923c",  # action_decode — orange
    "#22d3ee",  # serialize   — cyan
    "#4ade80",  # network_out — green
]

REQUESTS = {
    "standard_predict": {
        "label": "standard_predict (p50)",
        "total_ms": 226,
        "stages": {
            "network_in": 2.1, "auth": 0.8, "deserialize": 1.2,
            "preprocess": 8.2, "tokenize": 12.4, "vit_encode": 48.7,
            "llm_forward": 142.3, "action_decode": 9.8,
            "serialize": 0.9, "network_out": 2.1,
        },
    },
    "batch_predict_4": {
        "label": "batch_predict_4 (p50)",
        "total_ms": 847,
        "stages": {
            "network_in": 2.1, "auth": 0.8, "deserialize": 4.8,
            "preprocess": 31.4, "tokenize": 48.7, "vit_encode": 184.2,
            "llm_forward": 541.2, "action_decode": 38.7,
            "serialize": 3.6, "network_out": 2.1,
        },
    },
    "embed_only": {
        "label": "embed_only (p50)",
        "total_ms": 48,
        "stages": {
            "network_in": 2.1, "auth": 0.8, "deserialize": 1.2,
            "preprocess": 8.2, "tokenize": 12.4, "vit_encode": 21.4,
            "llm_forward": 0.0, "action_decode": 0.0,
            "serialize": 0.9, "network_out": 2.1,
        },
    },
}

OPTIMIZATION_TARGETS = [
    {
        "stage": "llm_forward",
        "technique": "FP8 quantization",
        "reduction_pct": 30,
        "baseline_ms": 142.3,
        "projected_ms": 99.0,
    },
    {
        "stage": "vit_encode",
        "technique": "TensorRT compilation",
        "reduction_pct": 20,
        "baseline_ms": 48.7,
        "projected_ms": 39.0,
    },
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _waterfall_svg(width: int = 680, row_h: int = 80) -> str:
    """3-row waterfall chart — one row per request type."""
    pad_left, pad_right, pad_top, pad_bottom = 160, 20, 30, 40
    chart_w = width - pad_left - pad_right
    n_rows = len(REQUESTS)
    height = pad_top + n_rows * row_h + pad_bottom

    max_ms = 600.0  # x-axis cap for readability (batch row clips, shown with label)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;border-radius:8px">')

    # Title
    lines.append(f'<text x="{width//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Per-Request Latency Waterfall (ms)</text>')

    # X-axis ticks
    tick_ms = [0, 100, 200, 300, 400, 500, 600]
    for t in tick_ms:
        x = pad_left + int(t / max_ms * chart_w)
        y_top = pad_top
        y_bot = pad_top + n_rows * row_h
        lines.append(f'<line x1="{x}" y1="{y_top}" x2="{x}" y2="{y_bot}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x}" y="{y_bot + 14}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{t}</text>')

    for row_idx, (rtype, rdata) in enumerate(REQUESTS.items()):
        y_row = pad_top + row_idx * row_h
        bar_h = 28
        bar_y = y_row + (row_h - bar_h) // 2

        # Row label
        lines.append(f'<text x="{pad_left - 8}" y="{bar_y + bar_h//2 + 4}" text-anchor="end" fill="#cbd5e1" font-size="10" font-family="monospace">{rdata["label"]}</text>')

        # Total label after bar
        lines.append(f'<text x="{pad_left + min(1.0, rdata["total_ms"]/max_ms)*chart_w + 4}" y="{bar_y + bar_h//2 + 4}" fill="#e2e8f0" font-size="10" font-family="monospace">{rdata["total_ms"]}ms</text>')

        cursor_x = 0.0
        for s_idx, stage in enumerate(STAGES):
            dur = rdata["stages"].get(stage, 0.0)
            if dur <= 0:
                continue
            seg_start = pad_left + int(min(cursor_x, max_ms) / max_ms * chart_w)
            seg_end   = pad_left + int(min(cursor_x + dur, max_ms) / max_ms * chart_w)
            seg_w = seg_end - seg_start
            color = STAGE_COLORS[s_idx]
            lines.append(f'<rect x="{seg_start}" y="{bar_y}" width="{seg_w}" height="{bar_h}" fill="{color}" stroke="#0f172a" stroke-width="1"/>')
            if seg_w >= 22:
                label = stage.replace("_", "\u00ad")  # soft-hyphen hint
                short = stage[:6] if seg_w < 50 else stage
                lines.append(f'<text x="{seg_start + seg_w//2}" y="{bar_y + bar_h//2 + 4}" text-anchor="middle" fill="#0f172a" font-size="9" font-family="monospace" font-weight="bold">{short}</text>')
            cursor_x += dur

    # Legend (bottom)
    leg_y = pad_top + n_rows * row_h + 28
    lx = pad_left
    for i, stage in enumerate(STAGES):
        if lx + 90 > width:
            break
        lines.append(f'<rect x="{lx}" y="{leg_y - 9}" width="10" height="10" fill="{STAGE_COLORS[i]}"/>')
        lines.append(f'<text x="{lx + 13}" y="{leg_y}" fill="#94a3b8" font-size="9" font-family="monospace">{stage}</text>')
        lx += len(stage) * 7 + 18

    lines.append('</svg>')
    return '\n'.join(lines)


def _stacked_pct_svg(width: int = 680, height: int = 200) -> str:
    """100% stacked horizontal bars per request type."""
    pad_left, pad_right, pad_top, pad_bottom = 160, 20, 30, 40
    chart_w = width - pad_left - pad_right
    n_rows = len(REQUESTS)
    bar_area = height - pad_top - pad_bottom
    bar_h = min(36, bar_area // n_rows - 10)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;border-radius:8px">')
    lines.append(f'<text x="{width//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Stage % of Total Latency</text>')

    for row_idx, (rtype, rdata) in enumerate(REQUESTS.items()):
        total = sum(rdata["stages"].values()) or 1.0
        y_bar = pad_top + row_idx * (bar_h + 12)

        lines.append(f'<text x="{pad_left - 8}" y="{y_bar + bar_h//2 + 4}" text-anchor="end" fill="#cbd5e1" font-size="10" font-family="monospace">{rdata["label"]}</text>')

        cursor = 0.0
        for s_idx, stage in enumerate(STAGES):
            dur = rdata["stages"].get(stage, 0.0)
            if dur <= 0:
                continue
            frac = dur / total
            seg_w = int(frac * chart_w)
            x = pad_left + int(cursor / total * chart_w)
            color = STAGE_COLORS[s_idx]
            lines.append(f'<rect x="{x}" y="{y_bar}" width="{seg_w}" height="{bar_h}" fill="{color}" stroke="#0f172a" stroke-width="1"/>')
            if seg_w >= 30:
                pct = round(frac * 100, 1)
                lines.append(f'<text x="{x + seg_w//2}" y="{y_bar + bar_h//2 + 4}" text-anchor="middle" fill="#0f172a" font-size="9" font-family="monospace" font-weight="bold">{pct}%</text>')
            cursor += dur

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Latency Breakdown", version="1.0.0")
else:
    app = None  # type: ignore


def _dashboard_html() -> str:
    wf_svg = _waterfall_svg()
    pct_svg = _stacked_pct_svg()

    opt_rows = ""
    for t in OPTIMIZATION_TARGETS:
        saving = t["baseline_ms"] - t["projected_ms"]
        opt_rows += f"""
        <tr>
          <td style='padding:8px 12px;color:#38bdf8;font-family:monospace'>{t['stage']}</td>
          <td style='padding:8px 12px;color:#94a3b8'>{t['technique']}</td>
          <td style='padding:8px 12px;color:#e2e8f0'>{t['baseline_ms']}ms</td>
          <td style='padding:8px 12px;color:#4ade80'>{t['projected_ms']}ms</td>
          <td style='padding:8px 12px;color:#C74634'>-{t['reduction_pct']}% (-{saving:.1f}ms)</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Latency Breakdown — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px; }}
    h1 {{ color:#38bdf8; font-size:22px; margin-bottom:4px; }}
    .subtitle {{ color:#64748b; font-size:13px; margin-bottom:24px; }}
    .card {{ background:#1e293b; border-radius:10px; padding:20px; margin-bottom:20px; }}
    h2 {{ color:#C74634; font-size:15px; margin:0 0 14px 0; }}
    table {{ border-collapse:collapse; width:100%; }}
    th {{ background:#0f172a; color:#94a3b8; padding:8px 12px; text-align:left; font-size:12px; }}
    tr:hover td {{ background:#263148; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; }}
    .note {{ color:#64748b; font-size:12px; margin-top:10px; }}
  </style>
</head>
<body>
  <h1>Latency Breakdown Waterfall</h1>
  <div class='subtitle'>OCI Robot Cloud — Inference Profiling Dashboard — Port 8188</div>

  <div class='card'>
    <h2>Per-Stage Waterfall (cascading)</h2>
    {wf_svg}
    <p class='note'>X-axis capped at 600ms for readability; batch_predict_4 total = 857ms shown after bar.</p>
  </div>

  <div class='card'>
    <h2>Stage Share of Total Latency</h2>
    {pct_svg}
    <p class='note'>llm_forward dominates standard_predict at 62.9%; drops to 63.9% in batch mode.</p>
  </div>

  <div class='card'>
    <h2>Optimization Targets</h2>
    <table>
      <thead><tr>
        <th>Stage</th><th>Technique</th>
        <th>Baseline</th><th>Projected</th><th>Saving</th>
      </tr></thead>
      <tbody>{opt_rows}</tbody>
    </table>
    <p class='note'>Combined optimizations: projected p50 standard_predict ≈ 170ms (from 226ms baseline).</p>
  </div>

  <div class='card'>
    <h2>API Endpoints</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/</td><td>This dashboard</td></tr>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/requests</td><td>All 3 request type profiles (JSON)</td></tr>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/breakdown/{{request_type}}</td><td>Single request breakdown</td></tr>
        <tr><td style='color:#4ade80'>GET</td><td style='color:#38bdf8'>/optimization-targets</td><td>Projected optimizations</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>"""


if app is not None:
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/requests")
    def get_requests():
        result = {}
        for rtype, rdata in REQUESTS.items():
            total = sum(rdata["stages"].values())
            pcts = {s: round(v / total * 100, 2) for s, v in rdata["stages"].items()}
            result[rtype] = {
                "label": rdata["label"],
                "total_ms": rdata["total_ms"],
                "stages_ms": rdata["stages"],
                "stages_pct": pcts,
            }
        return JSONResponse(result)

    @app.get("/breakdown/{request_type}")
    def get_breakdown(request_type: str):
        if request_type not in REQUESTS:
            return JSONResponse(
                {"error": f"Unknown request type '{request_type}'",
                 "valid": list(REQUESTS.keys())},
                status_code=404,
            )
        rdata = REQUESTS[request_type]
        total = sum(rdata["stages"].values())
        breakdown = []
        cumulative = 0.0
        for stage in STAGES:
            dur = rdata["stages"].get(stage, 0.0)
            breakdown.append({
                "stage": stage,
                "duration_ms": dur,
                "pct_of_total": round(dur / total * 100, 2) if total else 0,
                "cumulative_ms": round(cumulative + dur, 2),
            })
            cumulative += dur
        return JSONResponse({
            "request_type": request_type,
            "label": rdata["label"],
            "total_ms": rdata["total_ms"],
            "stage_sum_ms": round(total, 2),
            "breakdown": breakdown,
        })

    @app.get("/optimization-targets")
    def get_optimization_targets():
        baseline_total = REQUESTS["standard_predict"]["total_ms"]
        total_saving = sum(
            t["baseline_ms"] - t["projected_ms"] for t in OPTIMIZATION_TARGETS
        )
        return JSONResponse({
            "targets": OPTIMIZATION_TARGETS,
            "standard_predict_baseline_ms": baseline_total,
            "projected_p50_ms": round(baseline_total - total_saving, 1),
            "total_saving_ms": round(total_saving, 1),
        })


if __name__ == "__main__":
    if uvicorn and app:
        uvicorn.run(app, host="0.0.0.0", port=8188)
    else:
        print("FastAPI/uvicorn not installed. pip install fastapi uvicorn")
