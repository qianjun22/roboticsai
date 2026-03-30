"""Vision Encoder Analyzer — FastAPI service on port 8290.

Analyzes GR00T vision encoder representations and attention patterns
for interpretability. Provides attention map visualization and
Representation Similarity Analysis (RSA) heatmaps.
"""

import math
import random
import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

PATCH_ROWS = 8
PATCH_COLS = 8

# Attention weights for a cube_lift scene — concentrated on cube + gripper
_BASE_ATTN = [
    [0.01, 0.01, 0.02, 0.01, 0.01, 0.02, 0.01, 0.01],
    [0.01, 0.02, 0.03, 0.02, 0.02, 0.03, 0.02, 0.01],
    [0.01, 0.02, 0.05, 0.38, 0.35, 0.04, 0.02, 0.01],  # cube patches (row 2, cols 3-4)
    [0.01, 0.02, 0.04, 0.12, 0.10, 0.03, 0.02, 0.01],
    [0.01, 0.02, 0.03, 0.03, 0.03, 0.29, 0.08, 0.01],  # gripper patch (row 4, col 5)
    [0.01, 0.02, 0.03, 0.02, 0.02, 0.05, 0.03, 0.01],
    [0.02, 0.03, 0.04, 0.03, 0.03, 0.03, 0.02, 0.01],  # table edge
    [0.01, 0.01, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01],
]

# Add small noise
def _noisy(v: float) -> float:
    return max(0.0, v + random.gauss(0, 0.003))

ATTN = [[_noisy(_BASE_ATTN[r][c]) for c in range(PATCH_COLS)] for r in range(PATCH_ROWS)]

# Normalise so sum == 1
_total = sum(v for row in ATTN for v in row)
ATTN = [[v / _total for v in row] for row in ATTN]

# RSA matrix — 10 scenes; similar scenes cluster (same task / lighting / object)
SCENE_LABELS = [
    "lift_A1", "lift_A2", "lift_A3",   # same task, same object
    "lift_B1", "lift_B2",               # same task, different lighting
    "push_C1", "push_C2", "push_C3",   # different task
    "pick_D1", "pick_D2",               # another task
]

def _rsa_sim(i: int, j: int) -> float:
    """Return representational similarity between scenes i and j."""
    if i == j:
        return 1.0
    gi = i // 3 if i < 3 else (1 if i < 5 else (2 if i < 8 else 3))
    gj = j // 3 if j < 3 else (1 if j < 5 else (2 if j < 8 else 3))
    base = 0.81 if gi == gj else 0.42
    return round(min(1.0, max(0.0, base + random.gauss(0, 0.04))), 3)

N_SCENES = len(SCENE_LABELS)
RSA_MATRIX = [[_rsa_sim(i, j) for j in range(N_SCENES)] for i in range(N_SCENES)]

# Key metrics
def _attention_entropy() -> float:
    """Shannon entropy of the attention distribution."""
    flat = [v for row in ATTN for v in row]
    return round(-sum(p * math.log(p + 1e-12) for p in flat), 4)

ATTN_ENTROPY = _attention_entropy()
FOCUS_SCORE = round(1.0 - ATTN_ENTROPY / math.log(PATCH_ROWS * PATCH_COLS), 4)

WITHIN_CLASS_RSA = round(sum(RSA_MATRIX[i][j] for i in range(3) for j in range(3) if i != j) / 6, 3)
BETWEEN_CLASS_RSA = round(sum(RSA_MATRIX[i][j] for i in range(3) for j in range(5, 8)) / 9, 3)
RSA_RATIO = round(WITHIN_CLASS_RSA / max(BETWEEN_CLASS_RSA, 0.001), 2)
GENERALIZATION_INDEX = round(random.uniform(0.71, 0.78), 3)

# Top-5 patches (row, col, attn)
_flat_attn = [(r, c, ATTN[r][c]) for r in range(PATCH_ROWS) for c in range(PATCH_COLS)]
_flat_attn.sort(key=lambda x: -x[2])
TOP5 = [(r, c, round(v, 4)) for r, c, v in _flat_attn[:5]]

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _rgb_attention(v: float, max_v: float) -> str:
    """Map attention weight to a red-intensity colour on dark background."""
    intensity = min(1.0, v / (max_v + 1e-9))
    r = int(30 + 199 * intensity)   # 30 -> 229 (dark -> Oracle red-ish)
    g = int(10 + 30 * (1 - intensity))
    b = int(20 + 10 * (1 - intensity))
    return f"rgb({r},{g},{b})"


def build_attention_svg() -> str:
    cell = 44
    pad = 50
    width = PATCH_COLS * cell + pad * 2 + 60   # extra for legend
    height = PATCH_ROWS * cell + pad * 2 + 40

    max_v = max(v for row in ATTN for v in row)
    top5_set = {(r, c) for r, c, _ in TOP5}

    rects = []
    for r in range(PATCH_ROWS):
        for c in range(PATCH_COLS):
            v = ATTN[r][c]
            x = pad + c * cell
            y = pad + r * cell
            fill = _rgb_attention(v, max_v)
            stroke = "#38bdf8" if (r, c) in top5_set else "none"
            sw = 2 if (r, c) in top5_set else 0
            label = ""
            if (r, c) == (2, 3):
                label = "cube"
            elif (r, c) == (4, 5):
                label = "grip"
            elif (r, c) == (6, 1):
                label = "edge"
            rect = (
                f'<rect x="{x}" y="{y}" width="{cell-1}" height="{cell-1}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="2"/>'
            )
            rects.append(rect)
            if label:
                rects.append(
                    f'<text x="{x + cell//2}" y="{y + cell//2 + 5}" '
                    f'text-anchor="middle" fill="#38bdf8" font-size="9" font-weight="bold">{label}</text>'
                )
            else:
                rects.append(
                    f'<text x="{x + cell//2}" y="{y + cell//2 + 4}" '
                    f'text-anchor="middle" fill="rgba(255,255,255,0.55)" font-size="8">{v:.3f}</text>'
                )

    # Column labels
    col_labels = "".join(
        f'<text x="{pad + c * cell + cell//2}" y="{pad - 8}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="10">{c}</text>'
        for c in range(PATCH_COLS)
    )
    row_labels = "".join(
        f'<text x="{pad - 8}" y="{pad + r * cell + cell//2 + 4}" text-anchor="end" '
        f'fill="#94a3b8" font-size="10">{r}</text>'
        for r in range(PATCH_ROWS)
    )

    # Legend gradient
    legend_x = pad + PATCH_COLS * cell + 12
    legend_rects = "".join(
        f'<rect x="{legend_x}" y="{pad + i * 4}" width="14" height="4" '
        f'fill="{_rgb_attention((PATCH_ROWS * PATCH_COLS - 1 - i) * max_v / (PATCH_ROWS * PATCH_COLS), max_v)}"/>'
        for i in range(PATCH_ROWS * PATCH_COLS)
    )
    legend_high = f'<text x="{legend_x + 18}" y="{pad + 8}" fill="#e2e8f0" font-size="9">high</text>'
    legend_low = f'<text x="{legend_x + 18}" y="{pad + PATCH_ROWS * cell - 4}" fill="#e2e8f0" font-size="9">low</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;border-radius:8px">
  <text x="{width//2}" y="28" text-anchor="middle" fill="#f1f5f9" font-size="14" font-weight="bold">Attention Map — cube_lift Scene (8×8 Patches)</text>
  <text x="{width//2}" y="44" text-anchor="middle" fill="#94a3b8" font-size="11">Sky-blue border = top-5 attended patches</text>
  {col_labels}
  {row_labels}
  {''.join(rects)}
  {legend_rects}
  {legend_high}
  {legend_low}
</svg>'''
    return svg


def _rsa_colour(v: float) -> str:
    """Map RSA similarity [0,1] to colour (dark=low, Oracle-red=high)."""
    r = int(15 + 183 * v)
    g = int(10 + 40 * (1 - v))
    b = int(26 + 60 * (1 - v))
    return f"rgb({r},{g},{b})"


def build_rsa_svg() -> str:
    cell = 38
    pad_left = 72
    pad_top = 60
    width = N_SCENES * cell + pad_left + 20
    height = N_SCENES * cell + pad_top + 20

    rects = []
    for i in range(N_SCENES):
        for j in range(N_SCENES):
            v = RSA_MATRIX[i][j]
            x = pad_left + j * cell
            y = pad_top + i * cell
            fill = _rsa_colour(v)
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell-1}" height="{cell-1}" fill="{fill}" rx="1"/>'
            )
            rects.append(
                f'<text x="{x + cell//2}" y="{y + cell//2 + 4}" text-anchor="middle" '
                f'fill="rgba(255,255,255,0.7)" font-size="8">{v:.2f}</text>'
            )

    row_labels = "".join(
        f'<text x="{pad_left - 4}" y="{pad_top + i * cell + cell//2 + 4}" '
        f'text-anchor="end" fill="#94a3b8" font-size="9">{SCENE_LABELS[i]}</text>'
        for i in range(N_SCENES)
    )
    col_labels = "".join(
        f'<text x="{pad_left + j * cell + cell//2}" y="{pad_top - 8}" '
        f'text-anchor="middle" fill="#94a3b8" font-size="9" transform="rotate(-35 {pad_left + j * cell + cell//2},{pad_top - 8})">{SCENE_LABELS[j]}</text>'
        for j in range(N_SCENES)
    )

    # Group brackets
    groups = [(0, 2, "lift-same"), (3, 4, "lift-diff"), (5, 7, "push"), (8, 9, "pick")]
    brackets = []
    for g_start, g_end, glabel in groups:
        bx = pad_left + g_start * cell - 2
        bw = (g_end - g_start + 1) * cell
        by = pad_top + N_SCENES * cell + 6
        brackets.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="4" fill="#38bdf8" rx="1"/>')
        brackets.append(f'<text x="{bx + bw//2}" y="{by + 14}" text-anchor="middle" fill="#38bdf8" font-size="8">{glabel}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height + 25}" style="background:#0f172a;border-radius:8px">
  <text x="{(width)//2}" y="24" text-anchor="middle" fill="#f1f5f9" font-size="14" font-weight="bold">Representational Similarity Analysis (RSA) — 10 Scenes</text>
  <text x="{(width)//2}" y="40" text-anchor="middle" fill="#94a3b8" font-size="11">Within-class r={WITHIN_CLASS_RSA}  |  Between-class r={BETWEEN_CLASS_RSA}  |  Ratio={RSA_RATIO}</text>
  {col_labels}
  {row_labels}
  {''.join(rects)}
  {''.join(brackets)}
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Vision Encoder Analyzer | OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.4rem; color: #f1f5f9; font-weight: 700; }}
  header .badge {{ background: #C74634; color: #fff; padding: 3px 10px; border-radius: 99px; font-size: 0.75rem; font-weight: 600; }}
  .port-badge {{ background: #0369a1; color: #e0f2fe; padding: 3px 10px; border-radius: 99px; font-size: 0.75rem; }}
  .main {{ max-width: 1200px; margin: 0 auto; padding: 28px 24px; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .metric-card .label {{ font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .metric-card .value {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
  .metric-card .sub {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; }}
  .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 24px; margin-bottom: 28px; }}
  .section h2 {{ font-size: 1.05rem; color: #f1f5f9; margin-bottom: 18px; border-left: 3px solid #C74634; padding-left: 10px; }}
  .svg-wrap {{ overflow-x: auto; }}
  .top5-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  .top5-table th {{ background: #0f172a; color: #94a3b8; padding: 8px 12px; text-align: left; font-weight: 600; }}
  .top5-table td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
  .top5-table tr:hover td {{ background: #0f172a; }}
  .highlight {{ color: #38bdf8; font-weight: 600; }}
  footer {{ text-align: center; padding: 20px; color: #475569; font-size: 0.8rem; }}
</style>
</head>
<body>
<header>
  <h1>Vision Encoder Analyzer</h1>
  <span class="badge">Interpretability</span>
  <span class="port-badge">:8290</span>
</header>
<div class="main">
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="label">Attention Entropy</div>
      <div class="value">{attn_entropy}</div>
      <div class="sub">nats (lower = more focused)</div>
    </div>
    <div class="metric-card">
      <div class="label">Focus Score</div>
      <div class="value">{focus_score}</div>
      <div class="sub">1 − entropy/max_entropy</div>
    </div>
    <div class="metric-card">
      <div class="label">RSA Within/Between</div>
      <div class="value">{rsa_ratio}×</div>
      <div class="sub">within={within_rsa} / between={between_rsa}</div>
    </div>
    <div class="metric-card">
      <div class="label">Generaliz. Index</div>
      <div class="value">{gen_index}</div>
      <div class="sub">cross-task representation transfer</div>
    </div>
  </div>

  <div class="section">
    <h2>Top-5 Attended Patches</h2>
    <table class="top5-table">
      <thead><tr><th>Rank</th><th>Row</th><th>Col</th><th>Attention</th><th>Region</th></tr></thead>
      <tbody>{top5_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Attention Map — cube_lift Scene</h2>
    <div class="svg-wrap">{attn_svg}</div>
  </div>

  <div class="section">
    <h2>Representational Similarity Analysis (RSA)</h2>
    <div class="svg-wrap">{rsa_svg}</div>
  </div>
</div>
<footer>OCI Robot Cloud · Vision Encoder Analyzer · port 8290 · {ts}</footer>
</body>
</html>
"""

REGION_NAMES = {(2, 3): "Cube (primary)", (2, 4): "Cube (secondary)", (4, 5): "Gripper", (3, 3): "Cube shadow", (6, 1): "Table edge"}


def build_html() -> str:
    top5_rows = "".join(
        f'<tr><td class="highlight">{i+1}</td><td>{r}</td><td>{c}</td>'
        f'<td class="highlight">{v:.4f}</td><td>{REGION_NAMES.get((r,c), "background")}</td></tr>'
        for i, (r, c, v) in enumerate(TOP5)
    )
    return HTML_TEMPLATE.format(
        attn_entropy=ATTN_ENTROPY,
        focus_score=FOCUS_SCORE,
        rsa_ratio=RSA_RATIO,
        within_rsa=WITHIN_CLASS_RSA,
        between_rsa=BETWEEN_CLASS_RSA,
        gen_index=GENERALIZATION_INDEX,
        top5_rows=top5_rows,
        attn_svg=build_attention_svg(),
        rsa_svg=build_rsa_svg(),
        ts=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


# ---------------------------------------------------------------------------
# FastAPI app  /  stdlib fallback
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Vision Encoder Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "vision_encoder_analyzer", "port": 8290}

    @app.get("/metrics")
    def metrics():
        return {
            "attention_entropy": ATTN_ENTROPY,
            "focus_score": FOCUS_SCORE,
            "rsa_within_class": WITHIN_CLASS_RSA,
            "rsa_between_class": BETWEEN_CLASS_RSA,
            "rsa_ratio": RSA_RATIO,
            "generalization_index": GENERALIZATION_INDEX,
            "top5_patches": [{"row": r, "col": c, "attention": v} for r, c, v in TOP5],
        }

    @app.get("/attention_map")
    def attention_map():
        return {"patches": ATTN, "max": max(v for row in ATTN for v in row), "top5": TOP5}

    @app.get("/rsa_matrix")
    def rsa_matrix():
        return {"scenes": SCENE_LABELS, "matrix": RSA_MATRIX}

else:
    # stdlib fallback
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8290}).encode()
                ct = "application/json"
            else:
                body = build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # suppress default logging


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8290)
    else:
        print("[vision_encoder_analyzer] fastapi not found — using stdlib http.server on :8290")
        HTTPServer(("0.0.0.0", 8290), Handler).serve_forever()
