"""Multi-experiment statistical comparison with significance testing — port 8171."""

import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

EXPERIMENTS = [
    {"id": "exp_baseline",       "label": "Baseline BC",      "task": "cube_lift", "n": 20, "sr": 0.05, "mae": 0.103, "latency_ms": 412, "note": None},
    {"id": "exp_dagger_r9",      "label": "DAgger Run 9",     "task": "cube_lift", "n": 20, "sr": 0.71, "mae": 0.031, "latency_ms": 231, "note": None},
    {"id": "exp_groot_v2",       "label": "GR00T v2",         "task": "cube_lift", "n": 20, "sr": 0.78, "mae": 0.023, "latency_ms": 226, "note": None},
    {"id": "exp_groot_v3_partial","label": "GR00T v3 (40%)",  "task": "cube_lift", "n": 20, "sr": 0.62, "mae": 0.034, "latency_ms": 229, "note": "Partial training (40%)"},
]

# Pairwise z-test results (two-tailed proportion test, alpha=0.05)
PAIRWISE = [
    {"a": "exp_groot_v2",       "b": "exp_dagger_r9",       "z": 1.84,  "p": 0.033,   "significant": True,  "winner": "exp_groot_v2",       "delta_pp": 7},
    {"a": "exp_groot_v2",       "b": "exp_groot_v3_partial","z": 2.14,  "p": 0.016,   "significant": True,  "winner": "exp_groot_v2",       "delta_pp": 16},
    {"a": "exp_groot_v3_partial","b": "exp_dagger_r9",      "z": -1.12, "p": 0.131,   "significant": False, "winner": None,                "delta_pp": -9},
    {"a": "exp_dagger_r9",      "b": "exp_baseline",        "z": 8.97,  "p": 0.000001,"significant": True,  "winner": "exp_dagger_r9",      "delta_pp": 66},
]


def _se(sr, n):
    """Standard error for proportion."""
    return math.sqrt(sr * (1 - sr) / n)


def _lookup(exp_id):
    for e in EXPERIMENTS:
        if e["id"] == exp_id:
            return e
    return None


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _comparison_matrix_svg() -> str:
    """480×280 heatmap: 4×4 pairwise matrix."""
    W, H = 480, 280
    n = len(EXPERIMENTS)
    pad_l, pad_t = 110, 80
    cell = (W - pad_l - 16) / n
    cell_h = (H - pad_t - 16) / n

    ids = [e["id"] for e in EXPERIMENTS]
    labels = [e["label"] for e in EXPERIMENTS]

    # Build lookup for fast pairwise access
    result_map = {}
    for pw in PAIRWISE:
        result_map[(pw["a"], pw["b"])] = pw
        result_map[(pw["b"], pw["a"])] = {"a": pw["b"], "b": pw["a"], "z": -pw["z"],
                                            "p": pw["p"], "significant": pw["significant"],
                                            "winner": pw["winner"], "delta_pp": -pw["delta_pp"]}

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">')

    # Column headers (rotated)
    for j, lbl in enumerate(labels):
        cx = pad_l + j * cell + cell / 2
        lines.append(f'<text x="{cx:.1f}" y="{pad_t-8}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{lbl}</text>')

    # Row headers + cells
    for i, row_id in enumerate(ids):
        cy = pad_t + i * cell_h + cell_h / 2
        lines.append(f'<text x="{pad_l-6}" y="{cy+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{labels[i]}</text>')
        for j, col_id in enumerate(ids):
            rx = pad_l + j * cell
            ry = pad_t + i * cell_h
            rw = cell - 2
            rh = cell_h - 2
            if i == j:
                # Diagonal — blank
                lines.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="#1e293b" rx="3"/>')
                lines.append(f'<line x1="{rx:.1f}" y1="{ry:.1f}" x2="{rx+rw:.1f}" y2="{ry+rh:.1f}" stroke="#334155" stroke-width="1"/>')
            else:
                pw = result_map.get((row_id, col_id))
                if pw is None:
                    fill = "#1e293b"
                    label1 = "N/A"
                    label2 = ""
                elif not pw["significant"]:
                    fill = "#334155"  # gray — no winner
                    label1 = f"p={pw['p']:.3f}"
                    label2 = "n.s."
                elif pw["winner"] == row_id:
                    fill = "#7f1d1d"  # Oracle-red — row wins
                    label1 = f"p={pw['p']:.3f}"
                    label2 = f"+{abs(pw['delta_pp'])}pp \u25b2"
                else:
                    fill = "#0c4a6e"  # sky blue — col wins
                    label1 = f"p={pw['p']:.3f}"
                    label2 = f"-{abs(pw['delta_pp'])}pp \u25bc"
                lines.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="{fill}" rx="3"/>')
                if label1:
                    lines.append(f'<text x="{rx+rw/2:.1f}" y="{ry+rh/2-4:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="8" font-family="monospace">{label1}</text>')
                if label2:
                    lines.append(f'<text x="{rx+rw/2:.1f}" y="{ry+rh/2+8:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="8" font-family="monospace" font-weight="600">{label2}</text>')

    # Legend
    legend_y = H - 14
    items = [("#7f1d1d", "Row wins"), ("#0c4a6e", "Col wins"), ("#334155", "Not sig.")]
    lx = pad_l
    for color, text in items:
        lines.append(f'<rect x="{lx}" y="{legend_y-8}" width="10" height="8" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx+13}" y="{legend_y}" fill="#94a3b8" font-size="9" font-family="monospace">{text}</text>')
        lx += 80

    lines.append('</svg>')
    return '\n'.join(lines)


def _effect_size_svg() -> str:
    """680×200 SVG: SR per experiment with ±1.96×SE CI bars, sorted by SR."""
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 120, 20, 20, 36
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    sorted_exps = sorted(EXPERIMENTS, key=lambda e: e["sr"])
    n_exp = len(sorted_exps)
    max_sr = 1.0

    def x(sr):
        return pad_l + (sr / max_sr) * cw

    bar_h = ch / n_exp

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">')

    # X-axis grid
    for tick in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        tx = x(tick)
        lines.append(f'<line x1="{tx:.1f}" y1="{pad_t}" x2="{tx:.1f}" y2="{pad_t+ch}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{tx:.1f}" y="{H-6}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{int(tick*100)}%</text>')

    for i, exp in enumerate(sorted_exps):
        cy = pad_t + i * bar_h + bar_h / 2
        sr = exp["sr"]
        se = _se(sr, exp["n"])
        ci_lo = max(0.0, sr - 1.96 * se)
        ci_hi = min(1.0, sr + 1.96 * se)

        # CI bar
        lines.append(f'<line x1="{x(ci_lo):.1f}" y1="{cy:.1f}" x2="{x(ci_hi):.1f}" y2="{cy:.1f}" stroke="#38bdf8" stroke-width="2"/>')
        # Whisker caps
        lines.append(f'<line x1="{x(ci_lo):.1f}" y1="{cy-5}" x2="{x(ci_lo):.1f}" y2="{cy+5}" stroke="#38bdf8" stroke-width="1.5"/>')
        lines.append(f'<line x1="{x(ci_hi):.1f}" y1="{cy-5}" x2="{x(ci_hi):.1f}" y2="{cy+5}" stroke="#38bdf8" stroke-width="1.5"/>')
        # Point
        lines.append(f'<circle cx="{x(sr):.1f}" cy="{cy:.1f}" r="5" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>')

        # Label
        note = f" ({exp['note']})" if exp['note'] else ""
        lines.append(f'<text x="{pad_l-6}" y="{cy+4:.1f}" text-anchor="end" fill="#e2e8f0" font-size="9" font-family="monospace">{exp["label"]}{note}</text>')
        lines.append(f'<text x="{x(sr)+8:.1f}" y="{cy+4:.1f}" fill="#38bdf8" font-size="9" font-family="monospace" font-weight="600">{int(sr*100)}%</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    matrix_svg = _comparison_matrix_svg()
    effect_svg = _effect_size_svg()

    rows = ""
    for e in sorted(EXPERIMENTS, key=lambda x: -x["sr"]):
        se = _se(e["sr"], e["n"])
        ci_lo = max(0, e["sr"] - 1.96 * se)
        ci_hi = min(1.0, e["sr"] + 1.96 * se)
        note = f"<br><span style='color:#64748b;font-size:10px'>{e['note']}</span>" if e["note"] else ""
        rows += f'''
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 12px;color:#e2e8f0;font-size:13px">{e['label']}{note}</td>
            <td style="padding:10px 12px;text-align:center;color:#38bdf8;font-size:13px;font-weight:700">{int(e['sr']*100)}%</td>
            <td style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:12px">[{int(ci_lo*100)}%, {int(ci_hi*100)}%]</td>
            <td style="padding:10px 12px;text-align:center;color:#cbd5e1;font-size:12px">{e['mae']:.3f}</td>
            <td style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:12px">{e['latency_ms']}ms</td>
            <td style="padding:10px 12px;text-align:center;color:#64748b;font-size:12px">{e['n']}</td>
          </tr>'''

    pw_rows = ""
    for pw in PAIRWISE:
        a = _lookup(pw["a"])
        b = _lookup(pw["b"])
        sig_color = "#38bdf8" if pw["significant"] else "#64748b"
        sig_label = "YES" if pw["significant"] else "NO"
        w = _lookup(pw["winner"]) if pw["winner"] else None
        winner_str = w["label"] if w else "—"
        p_str = f"{pw['p']:.3f}" if pw["p"] >= 0.001 else "<0.001"
        pw_rows += f'''
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 12px;color:#e2e8f0;font-size:12px">{a['label']}</td>
            <td style="padding:10px 12px;color:#e2e8f0;font-size:12px">{b['label']}</td>
            <td style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:12px">{pw['z']:.2f}</td>
            <td style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:12px">{p_str}</td>
            <td style="padding:10px 12px;text-align:center"><span style="color:{sig_color};font-weight:700;font-size:12px">{sig_label}</span></td>
            <td style="padding:10px 12px;color:#38bdf8;font-size:12px">{winner_str} {'+'+str(abs(pw['delta_pp']))+'pp' if pw['winner'] else ''}</td>
          </tr>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Experiment Comparator — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f1f5f9; }}
    h2 {{ font-size: 15px; font-weight: 600; color: #94a3b8; margin: 24px 0 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .badge {{ display:inline-block; background:#C74634; color:#fff; font-size:11px; font-weight:700; padding:2px 8px; border-radius:4px; margin-left:8px; vertical-align:middle; }}
    table {{ width:100%; border-collapse:collapse; background:#0f1e33; border-radius:8px; overflow:hidden; }}
    th {{ padding:10px 12px; text-align:left; color:#64748b; font-size:11px; text-transform:uppercase; letter-spacing:.06em; background:#0a1628; }}
    tr:hover td {{ background:#132035; }}
    .card {{ background:#0f1e33; border-radius:8px; padding:20px; margin-bottom:24px; }}
    .insight {{ background:#0c2240; border-left:3px solid #38bdf8; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:24px; font-size:13px; line-height:1.6; color:#cbd5e1; }}
    .charts {{ display:grid; grid-template-columns:auto 1fr; gap:24px; align-items:start; }}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <div>
      <span style="color:#C74634;font-weight:700;font-size:13px;letter-spacing:.08em">OCI ROBOT CLOUD</span>
      <h1>Experiment Comparator <span class="badge">PORT 8171</span></h1>
    </div>
    <div style="color:#64748b;font-size:12px">{datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")} &bull; task: cube_lift &bull; &#x3B1;=0.05 (z-test)</div>
  </div>

  <div class="insight">
    <strong style="color:#38bdf8">Summary:</strong> <strong>GR00T v2</strong> is statistically superior to all other experiments (SR 78%, MAE 0.023, 226ms).
    GR00T v3 (partial training, 40%) not yet significantly different from DAgger Run 9 — needs more training steps.
    DAgger Run 9 shows massive improvement (+66pp) over baseline BC.
  </div>

  <h2>Experiments</h2>
  <table>
    <thead><tr>
      <th>Experiment</th><th>Success Rate</th><th>95% CI</th><th>MAE</th><th>Latency</th><th>N</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <h2>Pairwise Statistical Tests (z-test, two-tailed)</h2>
  <table>
    <thead><tr>
      <th>Experiment A</th><th>Experiment B</th><th>z</th><th>p-value</th><th>Significant?</th><th>Winner</th>
    </tr></thead>
    <tbody>{pw_rows}</tbody>
  </table>

  <h2>Comparison Matrix &amp; Effect Size</h2>
  <div class="charts">
    <div class="card" style="padding:16px">{matrix_svg}</div>
    <div>
      <div class="card" style="padding:16px">{effect_svg}</div>
    </div>
  </div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Experiment Comparator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/experiments")
    def experiments():
        return JSONResponse({"experiments": EXPERIMENTS})

    @app.get("/matrix")
    def matrix():
        return JSONResponse({"pairwise": PAIRWISE, "alpha": 0.05, "test": "z-test for proportions"})

    @app.get("/compare")
    def compare(a: str = "", b: str = ""):
        if not a or not b:
            return JSONResponse({"error": "Provide ?a=exp_id&b=exp_id"}, status_code=400)
        exp_a = _lookup(a)
        exp_b = _lookup(b)
        if not exp_a or not exp_b:
            return JSONResponse({"error": "Unknown experiment id"}, status_code=404)
        for pw in PAIRWISE:
            if (pw["a"] == a and pw["b"] == b) or (pw["a"] == b and pw["b"] == a):
                return JSONResponse({"pair": pw, "exp_a": exp_a, "exp_b": exp_b})
        return JSONResponse({"error": "Pairwise test not available for this pair"}, status_code=404)

if __name__ == "__main__":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed — run: pip install fastapi uvicorn")
    uvicorn.run("experiment_comparator:app", host="0.0.0.0", port=8171, reload=False)
