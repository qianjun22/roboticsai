"""Token Efficiency Analyzer — port 8297

Analyzes token and compute efficiency in GR00T's language-conditioned
action prediction. Visualizes token budget vs. success-rate tradeoffs.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

# Average token composition per inference request
TOKEN_BREAKDOWN = {
    "system_prompt":     42,
    "task_instruction":  89,
    "visual_tokens":    577,
    "history":           50,
    "action_tokens":     89,
}
TOTAL_TOKENS = sum(TOKEN_BREAKDOWN.values())  # 847

# Token budget experiment: (budget_pct, instruction_sr, visual_sr)
# budget_pct = % of default token allocation used for that component
BUDGET_EXPERIMENTS = [
    (50,  0.71, 0.66),
    (75,  0.77, 0.77),
    (100, 0.78, 0.78),
    (125, 0.78, 0.78),
]

# Compression findings
COMPRESSION = {
    "visual_pct_of_input": 68,
    "optimal_visual_budget_pct": 75,
    "sr_at_optimal": 0.77,
    "sr_at_100pct": 0.78,
    "sr_delta": -0.01,
    "compute_saved_pct": 31,
    "latency_saved_ms": 0.28,
    "cost_saved_per_request": 0.0003,
    "history_sr_at_50pct": 0.76,
}

KEY_METRICS = {
    "avg_tokens_per_request": TOTAL_TOKENS,
    "visual_token_compression_ratio": round(COMPRESSION["optimal_visual_budget_pct"] / 100, 2),
    "sr_cost_tradeoff": "SR −1% saves 31% compute at 75% visual budget",
    "optimal_token_budget": "75% visual tokens",
}


# ---------------------------------------------------------------------------
# SVG 1: Token Usage Breakdown — stacked bars per request type
# ---------------------------------------------------------------------------

def build_token_breakdown_svg() -> str:
    COLORS = {
        "system_prompt":     "#6366f1",
        "task_instruction":  "#38bdf8",
        "visual_tokens":     "#C74634",
        "history":           "#f59e0b",
        "action_tokens":     "#22c55e",
    }
    LABELS = {
        "system_prompt":     "System Prompt",
        "task_instruction":  "Task Instruction",
        "visual_tokens":     "Visual Tokens",
        "history":           "History",
        "action_tokens":     "Action Tokens",
    }

    width = 700
    bar_h = 56
    top_margin = 80
    left_margin = 20
    right_margin = 20
    legend_h = 130
    height = top_margin + bar_h + legend_h + 40
    bar_width = width - left_margin - right_margin

    keys = list(TOKEN_BREAKDOWN.keys())

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:10px;">',
        f'<text x="{width//2}" y="26" text-anchor="middle" '
        f'fill="#f1f5f9" font-size="15" font-weight="bold" font-family="monospace">'
        f'Token Usage Breakdown per Inference Request</text>',
        f'<text x="{width//2}" y="46" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace">'
        f'Avg {TOTAL_TOKENS} tokens/request · visual_tokens = {COMPRESSION["visual_pct_of_input"]}% of input</text>',
    ]

    # Stacked bar
    x_cursor = left_margin
    bar_y = top_margin
    for key in keys:
        count = TOKEN_BREAKDOWN[key]
        seg_w = int(count / TOTAL_TOKENS * bar_width)
        color = COLORS[key]
        svg_lines.append(
            f'<rect x="{x_cursor}" y="{bar_y}" width="{seg_w}" height="{bar_h}" fill="{color}" opacity="0.85"/>'
        )
        # Label inside segment if wide enough
        if seg_w > 42:
            svg_lines.append(
                f'<text x="{x_cursor + seg_w//2}" y="{bar_y + bar_h//2 - 6}" '
                f'text-anchor="middle" fill="#fff" font-size="10" font-family="monospace">{count}</text>'
            )
            svg_lines.append(
                f'<text x="{x_cursor + seg_w//2}" y="{bar_y + bar_h//2 + 9}" '
                f'text-anchor="middle" fill="#fff" font-size="9" font-family="monospace">'
                f'{round(count/TOTAL_TOKENS*100)}%</text>'
            )
        x_cursor += seg_w

    # Fill any rounding gap
    if x_cursor < left_margin + bar_width:
        svg_lines.append(
            f'<rect x="{x_cursor}" y="{bar_y}" width="{left_margin + bar_width - x_cursor}" '
            f'height="{bar_h}" fill="#334155"/>'
        )

    # Legend — 3 items per row
    leg_y = top_margin + bar_h + 24
    for i, key in enumerate(keys):
        col = i % 3
        row = i // 3
        lx = left_margin + col * 220
        ly = leg_y + row * 28
        color = COLORS[key]
        label = LABELS[key]
        count = TOKEN_BREAKDOWN[key]
        pct = round(count / TOTAL_TOKENS * 100)
        svg_lines.append(
            f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{color}" opacity="0.85"/>'
        )
        svg_lines.append(
            f'<text x="{lx + 20}" y="{ly + 11}" fill="#cbd5e1" font-size="11" font-family="monospace">'
            f'{label}: {count} ({pct}%)</text>'
        )

    # Compression callout
    callout_y = leg_y + 70
    svg_lines.append(
        f'<rect x="{left_margin}" y="{callout_y}" width="{bar_width}" height="26" rx="5" '
        f'fill="#C74634" opacity="0.15" stroke="#C74634" stroke-width="1"/>'
    )
    svg_lines.append(
        f'<text x="{left_margin + bar_width//2}" y="{callout_y + 17}" text-anchor="middle" '
        f'fill="#C74634" font-size="11" font-family="monospace">'
        f'Compression opportunity: visual_tokens ({COMPRESSION["visual_pct_of_input"]}% of input) '
        f'→ 75% budget saves 31% compute at SR cost of only -1%</text>'
    )

    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


# ---------------------------------------------------------------------------
# SVG 2: Efficiency vs SR line chart
# ---------------------------------------------------------------------------

def build_efficiency_svg() -> str:
    width = 700
    height = 360
    left_margin = 60
    right_margin = 30
    top_margin = 60
    bottom_margin = 60
    chart_w = width - left_margin - right_margin
    chart_h = height - top_margin - bottom_margin

    budgets = [b[0] for b in BUDGET_EXPERIMENTS]
    sr_instr = [b[1] for b in BUDGET_EXPERIMENTS]
    sr_visual = [b[2] for b in BUDGET_EXPERIMENTS]

    min_budget, max_budget = 50, 125
    min_sr, max_sr = 0.60, 0.82

    def x_pos(budget):
        return left_margin + int((budget - min_budget) / (max_budget - min_budget) * chart_w)

    def y_pos(sr):
        return top_margin + int((1 - (sr - min_sr) / (max_sr - min_sr)) * chart_h)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:10px;">',
        f'<text x="{width//2}" y="26" text-anchor="middle" '
        f'fill="#f1f5f9" font-size="15" font-weight="bold" font-family="monospace">'
        f'Token Budget vs. Success Rate</text>',
        f'<text x="{width//2}" y="46" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace">'
        f'Optimal: 75% visual tokens · SR=0.77 · saves 31% compute vs 100%</text>',
    ]

    # Grid lines
    for sr_tick in [0.65, 0.70, 0.75, 0.80]:
        gy = y_pos(sr_tick)
        svg_lines.append(
            f'<line x1="{left_margin}" y1="{gy}" x2="{left_margin + chart_w}" y2="{gy}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        svg_lines.append(
            f'<text x="{left_margin - 6}" y="{gy + 4}" text-anchor="end" '
            f'fill="#64748b" font-size="10" font-family="monospace">{sr_tick:.2f}</text>'
        )

    for b_tick in [50, 75, 100, 125]:
        gx = x_pos(b_tick)
        svg_lines.append(
            f'<line x1="{gx}" y1="{top_margin}" x2="{gx}" y2="{top_margin + chart_h}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        svg_lines.append(
            f'<text x="{gx}" y="{top_margin + chart_h + 16}" text-anchor="middle" '
            f'fill="#64748b" font-size="10" font-family="monospace">{b_tick}%</text>'
        )

    # Axes
    svg_lines.append(
        f'<line x1="{left_margin}" y1="{top_margin}" x2="{left_margin}" '
        f'y2="{top_margin + chart_h}" stroke="#475569" stroke-width="1.5"/>'
    )
    svg_lines.append(
        f'<line x1="{left_margin}" y1="{top_margin + chart_h}" '
        f'x2="{left_margin + chart_w}" y2="{top_margin + chart_h}" stroke="#475569" stroke-width="1.5"/>'
    )

    # Axis labels
    svg_lines.append(
        f'<text x="{left_margin + chart_w//2}" y="{height - 6}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace">Token Budget (% of default)</text>'
    )
    svg_lines.append(
        f'<text x="14" y="{top_margin + chart_h//2}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11" font-family="monospace" '
        f'transform="rotate(-90,14,{top_margin + chart_h//2})">Success Rate</text>'
    )

    # Instruction SR line (#38bdf8)
    instr_points = " ".join(f"{x_pos(b)},{y_pos(sr)}" for b, sr in zip(budgets, sr_instr))
    svg_lines.append(
        f'<polyline points="{instr_points}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>'
    )
    for b, sr in zip(budgets, sr_instr):
        svg_lines.append(
            f'<circle cx="{x_pos(b)}" cy="{y_pos(sr)}" r="5" fill="#38bdf8"/>'
        )
        svg_lines.append(
            f'<text x="{x_pos(b) + 8}" y="{y_pos(sr) - 6}" '
            f'fill="#38bdf8" font-size="9" font-family="monospace">{sr:.2f}</text>'
        )

    # Visual SR line (#C74634)
    visual_points = " ".join(f"{x_pos(b)},{y_pos(sr)}" for b, sr in zip(budgets, sr_visual))
    svg_lines.append(
        f'<polyline points="{visual_points}" fill="none" stroke="#C74634" stroke-width="2.5" '
        f'stroke-linejoin="round" stroke-dasharray="6,3"/>'
    )
    for b, sr in zip(budgets, sr_visual):
        svg_lines.append(
            f'<circle cx="{x_pos(b)}" cy="{y_pos(sr)}" r="5" fill="#C74634"/>'
        )
        svg_lines.append(
            f'<text x="{x_pos(b) + 8}" y="{y_pos(sr) + 14}" '
            f'fill="#C74634" font-size="9" font-family="monospace">{sr:.2f}</text>'
        )

    # Optimal marker at 75% visual
    opt_x = x_pos(75)
    opt_y = y_pos(0.77)
    svg_lines.append(
        f'<line x1="{opt_x}" y1="{top_margin}" x2="{opt_x}" y2="{top_margin + chart_h}" '
        f'stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.7"/>'
    )
    svg_lines.append(
        f'<text x="{opt_x + 4}" y="{top_margin + 14}" '
        f'fill="#22c55e" font-size="9" font-family="monospace">Optimal</text>'
    )

    # Legend
    leg_y = top_margin + chart_h - 30
    svg_lines.append(
        f'<line x1="{left_margin + 10}" y1="{leg_y}" x2="{left_margin + 34}" y2="{leg_y}" '
        f'stroke="#38bdf8" stroke-width="2.5"/>'
    )
    svg_lines.append(
        f'<text x="{left_margin + 40}" y="{leg_y + 4}" fill="#cbd5e1" font-size="11" font-family="monospace">Task Instruction budget</text>'
    )
    svg_lines.append(
        f'<line x1="{left_margin + 230}" y1="{leg_y}" x2="{left_margin + 254}" y2="{leg_y}" '
        f'stroke="#C74634" stroke-width="2.5" stroke-dasharray="6,3"/>'
    )
    svg_lines.append(
        f'<text x="{left_margin + 260}" y="{leg_y + 4}" fill="#cbd5e1" font-size="11" font-family="monospace">Visual token budget</text>'
    )

    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    breakdown_svg = build_token_breakdown_svg()
    efficiency_svg = build_efficiency_svg()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Token Efficiency Analyzer — Port 8297</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', monospace, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
    .metric-card {{ background: #1e293b; border-radius: 10px; padding: 18px; border-left: 4px solid #C74634; }}
    .metric-value {{ font-size: 2rem; font-weight: bold; color: #38bdf8; }}
    .metric-label {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .section-title {{ color: #e2e8f0; font-size: 1.1rem; margin-bottom: 12px; font-weight: 600; }}
    .chart-wrapper {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 28px; overflow-x: auto; }}
    .info-box {{ background: #1e293b; border-radius: 10px; padding: 18px; margin-bottom: 24px; border: 1px solid #334155; }}
    .info-box p {{ color: #cbd5e1; font-size: 0.88rem; line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{ background: #0f172a; color: #38bdf8; text-align: left; padding: 8px 12px; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
    tr:nth-child(even) td {{ background: #172033; }}
  </style>
</head>
<body>
  <h1>Token Efficiency Analyzer</h1>
  <p class="subtitle">Port 8297 · GR00T language-conditioned action prediction · Token budget optimization</p>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-value">{TOTAL_TOKENS}</div>
      <div class="metric-label">Avg Tokens / Request</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{COMPRESSION['visual_pct_of_input']}%</div>
      <div class="metric-label">Visual Token Share</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{COMPRESSION['optimal_visual_budget_pct']}%</div>
      <div class="metric-label">Optimal Visual Budget</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{COMPRESSION['compute_saved_pct']}%</div>
      <div class="metric-label">Compute Saved</div>
    </div>
  </div>

  <div class="section-title">Token Composition per Inference Request</div>
  <div class="chart-wrapper">{breakdown_svg}</div>

  <div class="section-title">Token Budget vs. Success Rate Tradeoff</div>
  <div class="chart-wrapper">{efficiency_svg}</div>

  <div class="info-box">
    <p><strong style="color:#38bdf8">Optimal strategy:</strong> Use 75% visual token budget — SR drops only 0.01 (0.78→0.77) while saving 31% compute, {COMPRESSION['latency_saved_ms']}ms latency, and ${COMPRESSION['cost_saved_per_request']}/request.</p>
    <p style="margin-top:8px"><strong style="color:#38bdf8">History compression:</strong> Reducing history to 50% budget yields SR=0.76 — acceptable for high-throughput scenarios.</p>
  </div>

  <div class="section-title">Budget Experiment Results</div>
  <div style="background:#1e293b;border-radius:10px;padding:16px;overflow-x:auto;">
    <table>
      <thead><tr><th>Budget (%)</th><th>Instruction SR</th><th>Visual SR</th><th>Visual Tokens</th><th>Compute vs 100%</th></tr></thead>
      <tbody>
        {''.join(f"<tr><td>{b}%</td><td>{si:.2f}</td><td>{sv:.2f}</td><td>{round(TOKEN_BREAKDOWN['visual_tokens']*b/100)}</td><td>{'−' if b<100 else '+' if b>100 else ''}{abs(b-100)}%</td></tr>" for b,si,sv in BUDGET_EXPERIMENTS)}
      </tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or fallback)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Token Efficiency Analyzer",
        description="Token and compute efficiency analysis for GR00T language-conditioned action prediction",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "token_efficiency_analyzer", "port": 8297}

    @app.get("/metrics")
    async def metrics():
        return {
            "avg_tokens_per_request": TOTAL_TOKENS,
            "token_breakdown": TOKEN_BREAKDOWN,
            "visual_token_pct": COMPRESSION["visual_pct_of_input"],
            "optimal_visual_budget_pct": COMPRESSION["optimal_visual_budget_pct"],
            "sr_at_optimal": COMPRESSION["sr_at_optimal"],
            "sr_at_100pct": COMPRESSION["sr_at_100pct"],
            "sr_delta": COMPRESSION["sr_delta"],
            "compute_saved_pct": COMPRESSION["compute_saved_pct"],
            "latency_saved_ms": COMPRESSION["latency_saved_ms"],
            "cost_saved_per_request_usd": COMPRESSION["cost_saved_per_request"],
        }

    @app.get("/experiments")
    async def experiments():
        return [
            {
                "budget_pct": b,
                "instruction_sr": si,
                "visual_sr": sv,
                "visual_tokens_used": round(TOKEN_BREAKDOWN["visual_tokens"] * b / 100),
                "compute_vs_baseline_pct": b - 100,
            }
            for b, si, sv in BUDGET_EXPERIMENTS
        ]

    @app.get("/recommend")
    async def recommend(scenario: str = "balanced"):
        """Return token budget recommendation for a scenario."""
        recs = {
            "balanced":   {"visual_budget_pct": 75,  "instruction_budget_pct": 100, "expected_sr": 0.77, "compute_saving_pct": 31},
            "throughput": {"visual_budget_pct": 50,  "instruction_budget_pct": 75,  "expected_sr": 0.70, "compute_saving_pct": 55},
            "quality":    {"visual_budget_pct": 100, "instruction_budget_pct": 125, "expected_sr": 0.78, "compute_saving_pct": 0},
        }
        if scenario not in recs:
            return {"error": f"Unknown scenario: {scenario}", "available": list(recs.keys())}
        return {"scenario": scenario, **recs[scenario]}

else:
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8297)
    else:
        server = http.server.HTTPServer(("0.0.0.0", 8297), _Handler)
        print("Token Efficiency Analyzer running on http://0.0.0.0:8297 (stdlib fallback)")
        server.serve_forever()
