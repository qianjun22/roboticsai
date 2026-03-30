"""Reward Hacking Detector — FastAPI port 8898"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8898

# Known hacking patterns
HACKING_PATTERNS = [
    {"name": "cube_corner_exploit", "detected": random.random() > 0.5, "episodes": random.randint(12, 48)},
    {"name": "gripper_open_cheat", "detected": random.random() > 0.6, "episodes": random.randint(8, 45)},
    {"name": "workspace_edge_bias", "detected": random.random() > 0.4, "episodes": random.randint(20, 49)},
]

def build_html():
    random.seed(42)
    # reward signal vs task_success rate across episodes
    rewards = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    sr_vals = [round(random.uniform(0.1, 0.6) * math.cos(i/4) + 0.4, 3) for i in range(10)]

    reward_bars = "".join(
        f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="14" height="{int(v*60)}" fill="#C74634"/>'
        for i, v in enumerate(rewards)
    )
    sr_bars = "".join(
        f'<rect x="{44+i*40}" y="{150-int(v*60)}" width="14" height="{int(v*60)}" fill="#38bdf8"/>'
        for i, v in enumerate(sr_vals)
    )

    divergence = round(sum(rewards) / len(rewards) - sum(sr_vals) / len(sr_vals), 3)
    alarm = divergence > 0.8
    alarm_color = "#ef4444" if alarm else "#22c55e"
    alarm_text = "ALARM: Hacking Detected" if alarm else "Normal — No Hacking"

    pattern_rows = "".join(
        f'<tr><td style="padding:6px 12px">{p["name"]}</td>'
        f'<td style="padding:6px 12px;color:{"#ef4444" if p["detected"] else "#22c55e"}">{"DETECTED" if p["detected"] else "clean"}</td>'
        f'<td style="padding:6px 12px">ep {p["episodes"]}</td></tr>'
        for p in HACKING_PATTERNS
    )

    return f"""<!DOCTYPE html><html><head><title>Reward Hacking Detector</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{text-align:left;padding:6px 12px;border-bottom:1px solid #334155}}
.alarm{{font-weight:bold;font-size:1.1em}}</style></head>
<body><h1>Reward Hacking Detector</h1>
<div class="card"><h2>Reward vs Task Success Divergence</h2>
<svg width="450" height="180">{reward_bars}{sr_bars}
<text x="30" y="170" fill="#C74634" font-size="11">Reward</text>
<text x="100" y="170" fill="#38bdf8" font-size="11">Task SR</text>
</svg>
<p>Mean Reward: {sum(rewards)/len(rewards):.3f} | Mean SR: {sum(sr_vals)/len(sr_vals):.3f} | Divergence: {divergence}</p>
<p class="alarm" style="color:{alarm_color}">{alarm_text}</p>
<p style="color:#94a3b8">Early alarm threshold: episode 50 | Port: {PORT}</p>
</div>
<div class="card"><h2>Known Hacking Patterns</h2>
<table><tr><th>Pattern</th><th>Status</th><th>First Seen</th></tr>{pattern_rows}</table>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Hacking Detector")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
