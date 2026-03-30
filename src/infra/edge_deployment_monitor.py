"""Edge Deployment Monitor — FastAPI port 8391"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8391

DEVICES = [
    {"name": "PI SF", "model": "groot_v2", "sr": 0.73, "latency": 231, "last_sync": "2h ago", "firmware": "JetPack5.1", "stale": False},
    {"name": "Apptronik Austin", "model": "groot_v1.6", "sr": 0.68, "latency": 248, "last_sync": "6h ago", "firmware": "JetPack5.0", "stale": False},
    {"name": "1X Stockholm", "model": "groot_v1.0", "sr": 0.58, "latency": 281, "last_sync": "3d ago", "firmware": "JetPack4.6", "stale": True},
]
CLOUD_SR = 0.78
COLORS = ["#38bdf8", "#a78bfa", "#fb923c"]
SYNC_LAG = {
    "PI SF":            [7, 8, 6, 9, 8, 7, 8],
    "Apptronik Austin": [11, 12, 10, 14, 13, 11, 12],
    "1X Stockholm":     [35, 42, 50, 61, 44, 55, 47],
}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def build_status_cards():
    W, H = 600, 160
    cw = W // 3
    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="0"/>')
    for i, d in enumerate(DEVICES):
        x = i * cw
        border = "#dc2626" if d["stale"] else "#334155"
        parts.append(f'<rect x="{x+4}" y="4" width="{cw-8}" height="{H-8}" fill="#1e293b" rx="8" stroke="{border}" stroke-width="2"/>')
        cx = x + cw // 2
        parts.append(f'<text x="{cx}" y="30" fill="{COLORS[i]}" font-size="12" font-weight="bold" text-anchor="middle" font-family="monospace">{d["name"]}</text>')
        parts.append(f'<text x="{cx}" y="50" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">{d["model"]}</text>')
        sr_col = "#16a34a" if d["sr"] >= 0.70 else ("#d97706" if d["sr"] >= 0.62 else "#dc2626")
        parts.append(f'<text x="{cx}" y="72" fill="{sr_col}" font-size="14" font-weight="bold" text-anchor="middle" font-family="monospace">SR {d["sr"]:.0%}</text>')
        parts.append(f'<text x="{cx}" y="92" fill="#64748b" font-size="10" text-anchor="middle" font-family="monospace">Latency {d["latency"]}ms</text>')
        sync_col = "#dc2626" if d["stale"] else "#94a3b8"
        stale_label = " ⚠ STALE" if d["stale"] else ""
        parts.append(f'<text x="{cx}" y="112" fill="{sync_col}" font-size="10" text-anchor="middle" font-family="monospace">Sync: {d["last_sync"]}{stale_label}</text>')
        parts.append(f'<text x="{cx}" y="132" fill="#475569" font-size="10" text-anchor="middle" font-family="monospace">{d["firmware"]}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def build_sr_bars():
    W, H = 480, 180
    lpad, rpad, tpad, bpad = 110, 20, 20, 30
    iW = W - lpad - rpad
    bh = 28
    gap = 8
    n_groups = len(DEVICES)
    group_h = 2 * bh + gap
    total_h = tpad + n_groups * (group_h + 10) + bpad
    parts = [f'<svg width="{W}" height="{total_h}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<rect width="{W}" height="{total_h}" fill="#1e293b" rx="8"/>')
    for i, d in enumerate(DEVICES):
        y0 = tpad + i * (group_h + 10)
        parts.append(f'<text x="{lpad-6}" y="{y0+bh//2+5}" fill="{COLORS[i]}" font-size="10" text-anchor="end" font-family="monospace">{d["name"]}</text>')
        w1 = int(d["sr"] * iW)
        parts.append(f'<rect x="{lpad}" y="{y0}" width="{w1}" height="{bh}" fill="{COLORS[i]}" rx="4" opacity="0.85"/>')
        parts.append(f'<text x="{lpad+w1+4}" y="{y0+bh//2+5}" fill="#e2e8f0" font-size="10" font-family="monospace">On-device {d["sr"]:.0%}</text>')
        y1 = y0 + bh + gap
        w2 = int(CLOUD_SR * iW)
        parts.append(f'<rect x="{lpad}" y="{y1}" width="{w2}" height="{bh}" fill="#334155" rx="4"/>')
        parts.append(f'<text x="{lpad+w2+4}" y="{y1+bh//2+5}" fill="#64748b" font-size="10" font-family="monospace">Cloud {CLOUD_SR:.0%}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def build_sync_timeline():
    W, H = 520, 200
    lpad, rpad, tpad, bpad = 50, 20, 20, 40
    iW = W - lpad - rpad
    iH = H - tpad - bpad
    max_lag = 65
    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    for gi in [0, 20, 40, 60]:
        gy = tpad + iH - int((gi / max_lag) * iH)
        parts.append(f'<line x1="{lpad}" y1="{gy}" x2="{W-rpad}" y2="{gy}" stroke="#334155" stroke-width="1"/>')
        parts.append(f'<text x="{lpad-4}" y="{gy+4}" fill="#64748b" font-size="10" text-anchor="end" font-family="monospace">{gi}m</text>')
    for xi, day in enumerate(DAYS):
        x = lpad + int(xi / (len(DAYS) - 1) * iW)
        parts.append(f'<text x="{x}" y="{H-10}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">{day}</text>')
    for i, (dname, lags) in enumerate(SYNC_LAG.items()):
        pts = []
        for xi, v in enumerate(lags):
            x = lpad + int(xi / (len(DAYS) - 1) * iW)
            y = tpad + iH - int((v / max_lag) * iH)
            pts.append((x, y))
        path = " ".join(f"{'M' if k == 0 else 'L'}{px},{py}" for k, (px, py) in enumerate(pts))
        parts.append(f'<path d="{path}" stroke="{COLORS[i]}" stroke-width="2.5" fill="none"/>')
        for px, py in pts:
            parts.append(f'<circle cx="{px}" cy="{py}" r="3" fill="{COLORS[i]}"/>')
        parts.append(f'<text x="{pts[-1][0]+5}" y="{pts[-1][1]+4}" fill="{COLORS[i]}" font-size="9" font-family="monospace">{dname.split()[0]}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def build_html():
    cards = build_status_cards()
    bars = build_sr_bars()
    timeline = build_sync_timeline()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Edge Deployment Monitor</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:20px 0 8px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px}}
.stat{{background:#1e293b;border-radius:8px;padding:12px 18px;min-width:160px}}
.stat .label{{color:#64748b;font-size:11px}}.stat .val{{color:#f1f5f9;font-size:16px;font-weight:bold}}
.warn{{color:#dc2626}}.ok{{color:#16a34a}}.mid{{color:#d97706}}
svg{{max-width:100%;display:block}}</style></head><body>
<h1>Edge Deployment Monitor</h1>
<p style="color:#64748b;font-size:12px">GR00T model deployments on Jetson edge devices — port {PORT}</p>
<div class="stats">
  <div class="stat"><div class="label">PI SF (groot_v2)</div><div class="val ok">SR 0.73 on-device</div><div class="label">vs 0.78 cloud (5pp gap)</div></div>
  <div class="stat"><div class="label">Apptronik (groot_v1.6)</div><div class="val mid">SR 0.68</div><div class="label">6h since last sync</div></div>
  <div class="stat"><div class="label">1X Stockholm (groot_v1.0)</div><div class="val warn">SR 0.58 OUTDATED</div><div class="label">3d stale — needs upgrade</div></div>
  <div class="stat"><div class="label">Avg Sync Lag</div><div class="val">14 min</div><div class="label">1X: 47min avg (network issues)</div></div>
</div>
<h2>Jetson Device Status Cards</h2>
{cards}
<h2>On-Device vs Cloud SR by Device</h2>
{bars}
<h2>Checkpoint Sync Lag — 7-Day Timeline</h2>
{timeline}
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Edge Deployment Monitor")
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
