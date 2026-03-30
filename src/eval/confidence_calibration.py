"""Model Confidence Calibration Analyzer — FastAPI service on port 8191.

Analyzes reliability / calibration of GR00T model predictions,
showing ECE, reliability diagrams, and temperature scaling impact.
"""

from __future__ import annotations

from typing import Any
from datetime import date

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install fastapi uvicorn") from e

app = FastAPI(title="Confidence Calibration Analyzer", version="1.0.0")

# ---------------------------------------------------------------------------
# Calibration data (200 inference samples, 10 bins)
# ---------------------------------------------------------------------------

CALIBRATION_BINS: list[dict[str, Any]] = [
    {"bin": "0.0-0.1", "low": 0.0, "high": 0.1, "mid": 0.05,
     "n_samples": 8,  "actual_accuracy": 0.00, "expected_accuracy": 0.05, "calibration_error": 0.05},
    {"bin": "0.1-0.2", "low": 0.1, "high": 0.2, "mid": 0.15,
     "n_samples": 12, "actual_accuracy": 0.08, "expected_accuracy": 0.15, "calibration_error": 0.07},
    {"bin": "0.2-0.3", "low": 0.2, "high": 0.3, "mid": 0.25,
     "n_samples": 18, "actual_accuracy": 0.17, "expected_accuracy": 0.25, "calibration_error": 0.08},
    {"bin": "0.3-0.4", "low": 0.3, "high": 0.4, "mid": 0.35,
     "n_samples": 22, "actual_accuracy": 0.31, "expected_accuracy": 0.35, "calibration_error": 0.04},
    {"bin": "0.4-0.5", "low": 0.4, "high": 0.5, "mid": 0.45,
     "n_samples": 28, "actual_accuracy": 0.43, "expected_accuracy": 0.45, "calibration_error": 0.02},
    {"bin": "0.5-0.6", "low": 0.5, "high": 0.6, "mid": 0.55,
     "n_samples": 24, "actual_accuracy": 0.54, "expected_accuracy": 0.55, "calibration_error": 0.01},
    {"bin": "0.6-0.7", "low": 0.6, "high": 0.7, "mid": 0.65,
     "n_samples": 31, "actual_accuracy": 0.68, "expected_accuracy": 0.65, "calibration_error": 0.03},
    {"bin": "0.7-0.8", "low": 0.7, "high": 0.8, "mid": 0.75,
     "n_samples": 27, "actual_accuracy": 0.81, "expected_accuracy": 0.75, "calibration_error": 0.06},
    {"bin": "0.8-0.9", "low": 0.8, "high": 0.9, "mid": 0.85,
     "n_samples": 19, "actual_accuracy": 0.89, "expected_accuracy": 0.85, "calibration_error": 0.04},
    {"bin": "0.9-1.0", "low": 0.9, "high": 1.0, "mid": 0.95,
     "n_samples": 11, "actual_accuracy": 0.91, "expected_accuracy": 0.95, "calibration_error": 0.04},
]

ECE_AFTER  = 0.041   # after temperature scaling T=1.8
ECE_BEFORE = 0.089   # before temperature scaling
TEMPERATURE = 1.8
TOTAL_SAMPLES = 200

# ---------------------------------------------------------------------------
# SVG color palette
# ---------------------------------------------------------------------------

_SKY   = "#38bdf8"
_RED   = "#C74634"
_BG    = "#0f172a"
_PANEL = "#1e293b"
_TEXT  = "#e2e8f0"
_MUTED = "#64748b"
_GREEN = "#22c55e"
_AMBER = "#f59e0b"
_WHITE = "#ffffff"

# ---------------------------------------------------------------------------
# SVG: Reliability diagram
# ---------------------------------------------------------------------------

def _reliability_svg(width: int = 680, height: int = 320) -> str:
    """Reliability diagram with bars (actual accuracy), perfect-calibration diagonal,
    and gap shading for over/under confidence."""
    pl, pr, pt, pb = 55, 30, 35, 50
    plot_w = width - pl - pr
    plot_h = height - pt - pb
    n = len(CALIBRATION_BINS)
    bar_w = plot_w / n
    gap = bar_w * 0.15

    def px(i: float) -> float:
        return pl + i * plot_w / n

    def py(v: float) -> float:
        return pt + plot_h * (1.0 - v)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:{_PANEL};border-radius:8px;">',
        f'<text x="{width/2}" y="20" text-anchor="middle" fill="{_TEXT}" '
        f'font-size="13" font-family="monospace">Reliability Diagram — GR00T Confidence Calibration</text>',
    ]

    # Grid
    for tick in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gy = py(tick)
        lines.append(
            f'<line x1="{pl}" y1="{gy:.1f}" x2="{pl+plot_w}" y2="{gy:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl-6}" y="{gy+4:.1f}" text-anchor="end" fill="{_MUTED}" '
            f'font-size="9" font-family="monospace">{tick:.1f}</text>'
        )

    # Bars + gap shading
    for i, b in enumerate(CALIBRATION_BINS):
        x0 = px(i) + gap / 2
        bw = bar_w - gap
        actual = b["actual_accuracy"]
        expected = b["expected_accuracy"]
        bar_top = py(actual)
        bar_bot = py(0.0)

        # Draw bar
        lines.append(
            f'<rect x="{x0:.1f}" y="{bar_top:.1f}" width="{bw:.1f}" '
            f'height="{bar_bot - bar_top:.1f}" fill="{_SKY}" opacity="0.85" rx="2"/>'
        )

        # Gap shading between actual and perfect diagonal (expected)
        diag_y = py(expected)
        if actual < expected:
            # under-confident: shaded above bar
            shade_top = bar_top
            shade_bot = diag_y
            shade_color = _AMBER
        else:
            # over-confident: shaded above bar
            shade_top = diag_y
            shade_bot = bar_top
            shade_color = _RED
        if abs(actual - expected) > 0.002:
            lines.append(
                f'<rect x="{x0:.1f}" y="{shade_top:.1f}" width="{bw:.1f}" '
                f'height="{abs(shade_bot - shade_top):.1f}" fill="{shade_color}" opacity="0.35" rx="1"/>'
            )

        # x-axis label
        cx = px(i) + bar_w / 2
        lines.append(
            f'<text x="{cx:.1f}" y="{pt+plot_h+14}" text-anchor="middle" fill="{_MUTED}" '
            f'font-size="8" font-family="monospace">{b["low"]:.1f}</text>'
        )

    # Perfect calibration diagonal (dashed white line)
    lines.append(
        f'<line x1="{pl}" y1="{py(0):.1f}" x2="{pl+plot_w}" y2="{py(1):.1f}" '
        f'stroke="white" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.6"/>'
    )

    # Axes labels
    lines.append(
        f'<text x="{pl+plot_w/2}" y="{pt+plot_h+32}" text-anchor="middle" '
        f'fill="{_TEXT}" font-size="11" font-family="monospace">Confidence</text>'
    )
    lines.append(
        f'<text x="16" y="{pt+plot_h/2}" text-anchor="middle" fill="{_TEXT}" '
        f'font-size="11" font-family="monospace" transform="rotate(-90,16,{pt+plot_h/2})">Accuracy</text>'
    )

    # ECE annotation
    lines.append(
        f'<text x="{pl+8}" y="{pt+16}" fill="{_GREEN}" font-size="10" font-family="monospace">'
        f'ECE = {ECE_AFTER} (T={TEMPERATURE})</text>'
    )

    # Legend
    legend_x = pl + plot_w - 200
    legend_y = pt + plot_h - 10
    items = [(_SKY, "Actual accuracy"), (_AMBER, "Under-confident"), (_RED, "Over-confident"),
             (_WHITE, "Perfect calibration")]
    for offset, (color, label) in enumerate(items):
        lx = legend_x
        ly = legend_y - offset * 16
        lines.append(f'<rect x="{lx}" y="{ly-8}" width="12" height="8" fill="{color}" opacity="0.85" rx="1"/>')
        lines.append(f'<text x="{lx+16}" y="{ly}" fill="{_MUTED}" font-size="9" font-family="monospace">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG: Calibration error by bin
# ---------------------------------------------------------------------------

def _error_bar_svg(width: int = 680, height: int = 180) -> str:
    """Bar chart of absolute calibration error per bin, with ECE annotation."""
    pl, pr, pt, pb = 55, 30, 30, 40
    plot_w = width - pl - pr
    plot_h = height - pt - pb
    n = len(CALIBRATION_BINS)
    bar_w = plot_w / n
    gap = bar_w * 0.2
    max_err = 0.12  # y-axis max

    def px(i: float) -> float:
        return pl + i * plot_w / n

    def py(v: float) -> float:
        return pt + plot_h * (1.0 - v / max_err)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:{_PANEL};border-radius:8px;">',
        f'<text x="{width/2}" y="18" text-anchor="middle" fill="{_TEXT}" '
        f'font-size="12" font-family="monospace">Calibration Error by Confidence Bin</text>',
    ]

    # Grid
    for tick in [0.02, 0.04, 0.06, 0.08, 0.10]:
        gy = py(tick)
        lines.append(
            f'<line x1="{pl}" y1="{gy:.1f}" x2="{pl+plot_w}" y2="{gy:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl-6}" y="{gy+4:.1f}" text-anchor="end" fill="{_MUTED}" '
            f'font-size="8" font-family="monospace">{tick:.2f}</text>'
        )

    for i, b in enumerate(CALIBRATION_BINS):
        x0 = px(i) + gap / 2
        bw = bar_w - gap
        err = b["calibration_error"]
        bar_top = py(err)
        bar_bot = py(0.0)
        lines.append(
            f'<rect x="{x0:.1f}" y="{bar_top:.1f}" width="{bw:.1f}" '
            f'height="{bar_bot - bar_top:.1f}" fill="{_RED}" rx="2"/>'
        )
        # value label
        cx = px(i) + bar_w / 2
        lines.append(
            f'<text x="{cx:.1f}" y="{bar_top - 3:.1f}" text-anchor="middle" '
            f'fill="{_TEXT}" font-size="8" font-family="monospace">{err:.2f}</text>'
        )
        lines.append(
            f'<text x="{cx:.1f}" y="{pt+plot_h+14}" text-anchor="middle" fill="{_MUTED}" '
            f'font-size="8" font-family="monospace">{b["low"]:.1f}</text>'
        )

    # ECE before line
    ece_before_y = py(ECE_BEFORE)
    lines.append(
        f'<line x1="{pl}" y1="{ece_before_y:.1f}" x2="{pl+plot_w}" y2="{ece_before_y:.1f}" '
        f'stroke="{_AMBER}" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )
    lines.append(
        f'<text x="{pl+plot_w-4}" y="{ece_before_y-4:.1f}" text-anchor="end" '
        f'fill="{_AMBER}" font-size="9" font-family="monospace">ECE before={ECE_BEFORE}</text>'
    )

    # ECE after line
    ece_after_y = py(ECE_AFTER)
    lines.append(
        f'<line x1="{pl}" y1="{ece_after_y:.1f}" x2="{pl+plot_w}" y2="{ece_after_y:.1f}" '
        f'stroke="{_GREEN}" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )
    lines.append(
        f'<text x="{pl+plot_w-4}" y="{ece_after_y-4:.1f}" text-anchor="end" '
        f'fill="{_GREEN}" font-size="9" font-family="monospace">ECE after={ECE_AFTER} (T={TEMPERATURE})</text>'
    )

    lines.append(
        f'<text x="{pl+plot_w/2}" y="{pt+plot_h+30}" text-anchor="middle" '
        f'fill="{_TEXT}" font-size="10" font-family="monospace">Confidence Bin</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG: Before/After temperature scaling overlay
# ---------------------------------------------------------------------------

def _before_after_svg(width: int = 680, height: int = 280) -> str:
    """Reliability diagram overlay: before (dashed amber) vs after (sky) temperature scaling."""
    pl, pr, pt, pb = 55, 30, 35, 50
    plot_w = width - pl - pr
    plot_h = height - pt - pb
    n = len(CALIBRATION_BINS)
    bar_w = plot_w / n

    def px_center(i: int) -> float:
        return pl + (i + 0.5) * plot_w / n

    def py(v: float) -> float:
        return pt + plot_h * (1.0 - v)

    # Simulate "before" calibration: scale errors by ECE_BEFORE/ECE_AFTER ratio
    ratio = ECE_BEFORE / ECE_AFTER  # ~2.17
    before_acc = [
        max(0.0, min(1.0, b["expected_accuracy"] - b["calibration_error"] * ratio))
        for b in CALIBRATION_BINS
    ]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:{_PANEL};border-radius:8px;">',
        f'<text x="{width/2}" y="20" text-anchor="middle" fill="{_TEXT}" '
        f'font-size="12" font-family="monospace">Temperature Scaling: Before vs After (T={TEMPERATURE})</text>',
    ]

    # Grid
    for tick in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gy = py(tick)
        lines.append(
            f'<line x1="{pl}" y1="{gy:.1f}" x2="{pl+plot_w}" y2="{gy:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl-6}" y="{gy+4:.1f}" text-anchor="end" fill="{_MUTED}" '
            f'font-size="9" font-family="monospace">{tick:.1f}</text>'
        )

    # Perfect diagonal
    lines.append(
        f'<line x1="{pl}" y1="{py(0):.1f}" x2="{pl+plot_w}" y2="{py(1):.1f}" '
        f'stroke="white" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.5"/>'
    )

    # Before line (amber dashed)
    pts_before = " ".join(f"{px_center(i):.1f},{py(v):.1f}" for i, v in enumerate(before_acc))
    lines.append(f'<polyline points="{pts_before}" fill="none" stroke="{_AMBER}" stroke-width="2" stroke-dasharray="6,3"/>')
    for i, v in enumerate(before_acc):
        lines.append(
            f'<circle cx="{px_center(i):.1f}" cy="{py(v):.1f}" r="3" fill="{_AMBER}"/>'
        )

    # After line (sky)
    pts_after = " ".join(f"{px_center(i):.1f},{py(b['actual_accuracy']):.1f}" for i, b in enumerate(CALIBRATION_BINS))
    lines.append(f'<polyline points="{pts_after}" fill="none" stroke="{_SKY}" stroke-width="2"/>')
    for i, b in enumerate(CALIBRATION_BINS):
        lines.append(
            f'<circle cx="{px_center(i):.1f}" cy="{py(b["actual_accuracy"]):.1f}" r="3" fill="{_SKY}"/>'
        )

    # x-axis labels
    for i, b in enumerate(CALIBRATION_BINS):
        lines.append(
            f'<text x="{px_center(i):.1f}" y="{pt+plot_h+14}" text-anchor="middle" '
            f'fill="{_MUTED}" font-size="8" font-family="monospace">{b["low"]:.1f}</text>'
        )

    # Axes
    lines.append(
        f'<text x="{pl+plot_w/2}" y="{pt+plot_h+32}" text-anchor="middle" '
        f'fill="{_TEXT}" font-size="10" font-family="monospace">Confidence</text>'
    )
    lines.append(
        f'<text x="16" y="{pt+plot_h/2}" text-anchor="middle" fill="{_TEXT}" '
        f'font-size="10" font-family="monospace" transform="rotate(-90,16,{pt+plot_h/2})">Accuracy</text>'
    )

    # Legend
    lx = pl + 10
    ly = pt + 16
    lines.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+20}" y2="{ly}" stroke="{_AMBER}" stroke-width="2" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{lx+24}" y="{ly+4}" fill="{_AMBER}" font-size="9" font-family="monospace">Before T-scaling (ECE={ECE_BEFORE})</text>')
    lines.append(f'<line x1="{lx+200}" y1="{ly}" x2="{lx+220}" y2="{ly}" stroke="{_SKY}" stroke-width="2"/>')
    lines.append(f'<text x="{lx+224}" y="{ly+4}" fill="{_SKY}" font-size="9" font-family="monospace">After T-scaling (ECE={ECE_AFTER})</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/calibration", response_class=JSONResponse)
async def get_calibration() -> dict[str, Any]:
    """Return per-bin calibration data."""
    return {
        "bins": CALIBRATION_BINS,
        "total_samples": TOTAL_SAMPLES,
        "ece_before_scaling": ECE_BEFORE,
        "ece_after_scaling": ECE_AFTER,
        "temperature": TEMPERATURE,
        "improvement_pct": round((ECE_BEFORE - ECE_AFTER) / ECE_BEFORE * 100, 1),
    }


@app.get("/ece", response_class=JSONResponse)
async def get_ece() -> dict[str, Any]:
    """Return ECE summary and temperature scaling details."""
    # Verify ECE via weighted mean
    n_total = sum(b["n_samples"] for b in CALIBRATION_BINS)
    ece_computed = sum(b["n_samples"] * b["calibration_error"] for b in CALIBRATION_BINS) / n_total
    return {
        "ece_after_scaling": ECE_AFTER,
        "ece_before_scaling": ECE_BEFORE,
        "ece_computed_from_bins": round(ece_computed, 4),
        "temperature": TEMPERATURE,
        "total_samples": TOTAL_SAMPLES,
        "improvement_pct": round((ECE_BEFORE - ECE_AFTER) / ECE_BEFORE * 100, 1),
        "best_calibrated_bin": "0.5-0.6",
        "worst_calibrated_bin": "0.2-0.3",
        "note": "Temperature scaling T=1.8 divides logits before softmax, softening overconfident predictions",
    }


@app.get("/diagram", response_class=HTMLResponse)
async def get_diagram() -> HTMLResponse:
    """Return SVG diagrams only (embeddable)."""
    r = _reliability_svg()
    e = _error_bar_svg()
    b = _before_after_svg()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:{_BG};padding:20px;">
{r}<br><br>{e}<br><br>{b}
</body></html>"""
    return HTMLResponse(content=html)


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    reliability_svg = _reliability_svg()
    error_svg = _error_bar_svg()
    before_after_svg = _before_after_svg()

    # Bin table rows
    bin_rows = ""
    for b in CALIBRATION_BINS:
        gap = b["actual_accuracy"] - b["expected_accuracy"]
        gap_label = f"+{gap:.2f} (over-conf)" if gap > 0.005 else (f"{gap:.2f} (under-conf)" if gap < -0.005 else "~calibrated")
        gap_color = _RED if gap > 0.005 else (_AMBER if gap < -0.005 else _GREEN)
        err_color = _RED if b["calibration_error"] >= 0.06 else (_AMBER if b["calibration_error"] >= 0.03 else _GREEN)
        bin_rows += f"""
        <tr>
          <td style="color:{_TEXT};padding:5px 10px;font-family:monospace;font-size:12px;">{b['bin']}</td>
          <td style="color:{_MUTED};padding:5px 10px;font-family:monospace;font-size:12px;text-align:center;">{b['n_samples']}</td>
          <td style="color:{_SKY};padding:5px 10px;font-family:monospace;font-size:12px;text-align:center;">{b['actual_accuracy']:.2f}</td>
          <td style="color:{_MUTED};padding:5px 10px;font-family:monospace;font-size:12px;text-align:center;">{b['expected_accuracy']:.2f}</td>
          <td style="color:{gap_color};padding:5px 10px;font-family:monospace;font-size:11px;">{gap_label}</td>
          <td style="color:{err_color};padding:5px 10px;font-family:monospace;font-size:12px;text-align:center;">{b['calibration_error']:.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confidence Calibration — GR00T</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {_BG}; color: {_TEXT}; font-family: monospace; padding: 24px; }}
    h1 {{ color: {_RED}; font-size: 22px; margin-bottom: 4px; }}
    h2 {{ color: {_SKY}; font-size: 14px; margin: 20px 0 10px; }}
    .subtitle {{ color: #64748b; font-size: 12px; margin-bottom: 24px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
    .metric {{ background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; }}
    .metric-val {{ font-size: 28px; font-weight: bold; margin: 6px 0 2px; }}
    .metric-label {{ color: #64748b; font-size: 11px; }}
    .svg-block {{ margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th {{ background: #0f172a; color: #64748b; padding: 7px 10px; text-align: left; font-size: 11px; }}
    tr:hover {{ background: #263548; }}
  </style>
</head>
<body>
  <h1>Confidence Calibration Analyzer</h1>
  <div class="subtitle">GR00T N1.6 — 200 inference samples · {date.today()}</div>

  <div class="metrics">
    <div class="metric">
      <div class="metric-label">ECE After Scaling</div>
      <div class="metric-val" style="color:{_GREEN}">{ECE_AFTER}</div>
      <div class="metric-label">temperature T={TEMPERATURE}</div>
    </div>
    <div class="metric">
      <div class="metric-label">ECE Before Scaling</div>
      <div class="metric-val" style="color:{_AMBER}">{ECE_BEFORE}</div>
      <div class="metric-label">raw logits</div>
    </div>
    <div class="metric">
      <div class="metric-label">ECE Improvement</div>
      <div class="metric-val" style="color:{_SKY}">53.9%</div>
      <div class="metric-label">via temperature scaling</div>
    </div>
    <div class="metric">
      <div class="metric-label">Best Calibrated Bin</div>
      <div class="metric-val" style="color:{_GREEN};font-size:18px;">0.5–0.6</div>
      <div class="metric-label">err=0.01</div>
    </div>
  </div>

  <h2>Reliability Diagram (After Temperature Scaling)</h2>
  <div class="svg-block">{reliability_svg}</div>

  <h2>Before vs After Temperature Scaling (T=1.8)</h2>
  <div class="svg-block">{before_after_svg}</div>

  <h2>Calibration Error by Bin</h2>
  <div class="svg-block">{error_svg}</div>

  <h2>Per-Bin Breakdown</h2>
  <table>
    <thead>
      <tr>
        <th>Confidence Bin</th><th style="text-align:center">N Samples</th>
        <th style="text-align:center">Actual Acc</th><th style="text-align:center">Expected Acc</th>
        <th>Gap</th><th style="text-align:center">Calib Error</th>
      </tr>
    </thead>
    <tbody>{bin_rows}</tbody>
  </table>

  <div style="margin-top:24px;color:#334155;font-size:10px;font-family:monospace;">
    API: /calibration · /ece · /diagram · port 8191
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8191)
