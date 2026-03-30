"""Distillation Benchmark Service — FastAPI port 8692"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8692

def build_html():
    # Generate distillation benchmark metrics with math/random
    random.seed(42)
    num_epochs = 20
    teacher_losses = [round(1.8 * math.exp(-0.18 * i) + random.uniform(-0.03, 0.03), 4) for i in range(num_epochs)]
    student_losses = [round(2.1 * math.exp(-0.15 * i) + random.uniform(-0.05, 0.05), 4) for i in range(num_epochs)]
    kd_losses = [round(0.9 * math.exp(-0.22 * i) + random.uniform(-0.02, 0.02), 4) for i in range(num_epochs)]

    chart_w, chart_h = 560, 220
    pad = 40
    x_scale = (chart_w - pad * 2) / (num_epochs - 1)
    y_min, y_max = 0.0, 2.3
    y_scale = (chart_h - pad * 2) / (y_max - y_min)

    def to_svg_pt(i, val):
        x = pad + i * x_scale
        y = chart_h - pad - (val - y_min) * y_scale
        return x, y

    def polyline(series, color):
        pts = " ".join(f"{to_svg_pt(i, v)[0]:.1f},{to_svg_pt(i, v)[1]:.1f}" for i, v in enumerate(series))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2"/>'

    teacher_svg = polyline(teacher_losses, "#38bdf8")
    student_svg = polyline(student_losses, "#f472b6")
    kd_svg = polyline(kd_losses, "#4ade80")

    # X axis ticks
    xticks = "".join(
        f'<text x="{pad + i * x_scale:.1f}" y="{chart_h - 8}" fill="#94a3b8" font-size="10" text-anchor="middle">{i+1}</text>'
        for i in range(0, num_epochs, 4)
    )
    # Y axis ticks
    yticks = "".join(
        f'<text x="{pad - 6}" y="{chart_h - pad - v * y_scale + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.1f}</text>'
        for v in [0.0, 0.5, 1.0, 1.5, 2.0]
    )
    # Horizontal grid lines
    grid = "".join(
        f'<line x1="{pad}" y1="{chart_h - pad - v * y_scale:.1f}" x2="{chart_w - pad}" y2="{chart_h - pad - v * y_scale:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
        for v in [0.0, 0.5, 1.0, 1.5, 2.0]
    )

    # Compression stats
    teacher_params = 3.0  # B
    student_params = round(random.uniform(0.28, 0.35), 2)
    compression_ratio = round(teacher_params / student_params, 1)
    fidelity = round(random.uniform(94.1, 97.8), 1)
    latency_teacher = round(random.uniform(220, 240), 1)
    latency_student = round(random.uniform(38, 48), 1)
    throughput_gain = round(latency_teacher / latency_student, 1)

    # Accuracy bar chart (tasks)
    tasks = ["PickPlace", "StackCube", "PegInsert", "DoorOpen", "DrawerClose"]
    teacher_acc = [round(random.uniform(88, 97), 1) for _ in tasks]
    student_acc = [round(ta * random.uniform(0.93, 0.99), 1) for ta in teacher_acc]

    bar_w, bar_h = 560, 200
    bar_pad = 50
    n_tasks = len(tasks)
    group_w = (bar_w - bar_pad * 2) / n_tasks
    bar_width = group_w * 0.35

    bars = ""
    for i, (task, ta, sa) in enumerate(zip(tasks, teacher_acc, student_acc)):
        gx = bar_pad + i * group_w
        bh_teacher = ta / 100 * (bar_h - bar_pad - 20)
        bh_student = sa / 100 * (bar_h - bar_pad - 20)
        bars += f'<rect x="{gx + group_w * 0.05:.1f}" y="{bar_h - bar_pad - bh_teacher:.1f}" width="{bar_width:.1f}" height="{bh_teacher:.1f}" fill="#38bdf8" rx="2"/>'
        bars += f'<rect x="{gx + group_w * 0.05 + bar_width + 3:.1f}" y="{bar_h - bar_pad - bh_student:.1f}" width="{bar_width:.1f}" height="{bh_student:.1f}" fill="#f472b6" rx="2"/>'
        bars += f'<text x="{gx + group_w * 0.5:.1f}" y="{bar_h - 8}" fill="#94a3b8" font-size="9" text-anchor="middle">{task}</text>'
        bars += f'<text x="{gx + group_w * 0.05 + bar_width * 0.5:.1f}" y="{bar_h - bar_pad - bh_teacher - 4:.1f}" fill="#38bdf8" font-size="9" text-anchor="middle">{ta}</text>'
        bars += f'<text x="{gx + group_w * 0.05 + bar_width + 3 + bar_width * 0.5:.1f}" y="{bar_h - bar_pad - bh_student - 4:.1f}" fill="#f472b6" font-size="9" text-anchor="middle">{sa}</text>'

    return f"""<!DOCTYPE html><html><head><title>Distillation Benchmark</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:24px 24px 0;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1.1rem;margin:0 0 12px}}
.subtitle{{color:#94a3b8;padding:4px 24px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:0 24px 16px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:0 24px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.label{{font-size:0.78rem;color:#64748b;margin-top:4px}}
.charts{{padding:0 24px 24px;display:grid;grid-template-columns:1fr 1fr;gap:16px}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Distillation Benchmark</h1>
<div class="subtitle">Teacher→Student knowledge distillation · GR00T N1.6 3B → {student_params}B · Port {PORT}</div>

<div class="grid4">
  <div class="card"><div class="stat">{student_params}B</div><div class="label">Student Params</div></div>
  <div class="card"><div class="stat">{compression_ratio}×</div><div class="label">Compression Ratio</div></div>
  <div class="card"><div class="stat">{fidelity}%</div><div class="label">Fidelity Score</div></div>
  <div class="card"><div class="stat">{throughput_gain}×</div><div class="label">Throughput Gain</div></div>
</div>

<div class="charts">
  <div class="card">
    <h2>Training Loss Curves (20 Epochs)</h2>
    <svg width="{chart_w}" height="{chart_h}" style="display:block">
      {grid}{teacher_svg}{student_svg}{kd_svg}{xticks}{yticks}
      <text x="{chart_w - pad}" y="{pad - 8}" fill="#94a3b8" font-size="10" text-anchor="end">Epoch</text>
      <!-- Legend -->
      <rect x="{pad}" y="10" width="10" height="10" fill="#38bdf8"/>
      <text x="{pad + 14}" y="19" fill="#e2e8f0" font-size="11">Teacher</text>
      <rect x="{pad + 75}" y="10" width="10" height="10" fill="#f472b6"/>
      <text x="{pad + 89}" y="19" fill="#e2e8f0" font-size="11">Student</text>
      <rect x="{pad + 155}" y="10" width="10" height="10" fill="#4ade80"/>
      <text x="{pad + 169}" y="19" fill="#e2e8f0" font-size="11">KD Loss</text>
    </svg>
  </div>
  <div class="card">
    <h2>Task Accuracy: Teacher vs Student</h2>
    <svg width="{bar_w}" height="{bar_h}" style="display:block">
      <line x1="{bar_pad}" y1="{bar_h - bar_pad}" x2="{bar_w - bar_pad}" y2="{bar_h - bar_pad}" stroke="#334155" stroke-width="1"/>
      {bars}
      <!-- Legend -->
      <rect x="{bar_pad}" y="10" width="10" height="10" fill="#38bdf8"/>
      <text x="{bar_pad + 14}" y="19" fill="#e2e8f0" font-size="11">Teacher</text>
      <rect x="{bar_pad + 75}" y="10" width="10" height="10" fill="#f472b6"/>
      <text x="{bar_pad + 89}" y="19" fill="#e2e8f0" font-size="11">Student</text>
    </svg>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Latency</h2>
    <div style="color:#94a3b8;font-size:0.85rem">Teacher: <span style="color:#38bdf8">{latency_teacher} ms</span></div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:6px">Student: <span style="color:#4ade80">{latency_student} ms</span></div>
  </div>
  <div class="card">
    <h2>Final Losses</h2>
    <div style="color:#94a3b8;font-size:0.85rem">Teacher: <span style="color:#38bdf8">{teacher_losses[-1]}</span></div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:4px">Student: <span style="color:#f472b6">{student_losses[-1]}</span></div>
    <div style="color:#94a3b8;font-size:0.85rem;margin-top:4px">KD: <span style="color:#4ade80">{kd_losses[-1]}</span></div>
  </div>
  <div class="card">
    <h2>Method</h2>
    <div style="color:#94a3b8;font-size:0.85rem">Response distillation + feature-level KL divergence · temperature=4.0 · α=0.7</div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Distillation Benchmark")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        random.seed(42)
        num_epochs = 20
        return {
            "teacher_params_B": 3.0,
            "student_params_B": round(random.uniform(0.28, 0.35), 2),
            "final_teacher_loss": round(1.8 * math.exp(-0.18 * (num_epochs - 1)), 4),
            "final_student_loss": round(2.1 * math.exp(-0.15 * (num_epochs - 1)), 4),
            "fidelity_pct": round(random.uniform(94.1, 97.8), 1),
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
