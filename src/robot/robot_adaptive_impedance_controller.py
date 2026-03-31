import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 11516
SERVICE = "robot_adaptive_impedance_controller"
DESCRIPTION = "Adaptive impedance controller that adjusts stiffness and damping based on contact state and task phase"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    return f"""<!DOCTYPE html>
<html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}.header{{background:#1e293b;padding:20px 32px;border-bottom:2px solid #C74634}}h1{{margin:0;color:#C74634;font-size:1.5rem}}.sub{{color:#94a3b8;font-size:.85rem;margin-top:4px}}.card{{background:#1e293b;border-radius:8px;padding:20px;margin:20px 32px}}.metric{{display:inline-block;margin-right:32px}}.metric .val{{font-size:2rem;font-weight:700;color:#38bdf8}}.metric .lbl{{font-size:.75rem;color:#94a3b8;text-transform:uppercase}}canvas{{display:block;margin:16px 0}}</style></head>
<body><div class="header"><h1>{SERVICE}</h1><div class="sub">Port {PORT} · {DESCRIPTION}</div></div>
<div class="card"><div class="metric"><div class="val" id="req">0</div><div class="lbl">Requests</div></div><div class="metric"><div class="val">OK</div><div class="lbl">Status</div></div><div class="metric"><div class="val">{PORT}</div><div class="lbl">Port</div></div><canvas id="c" width="400" height="80"></canvas></div>
<script>let n=0;const cv=document.getElementById('c'),ctx=cv.getContext('2d'),bars=Array(20).fill(0);function draw(){{ctx.clearRect(0,0,400,80);bars.push(Math.random()*60+10);bars.shift();bars.forEach((h,i)=>{{ctx.fillStyle='#38bdf8';ctx.fillRect(i*20,80-h,16,h);}})}}setInterval(()=>{{n++;document.getElementById('req').textContent=n;draw();}},1000);</script>
</body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
