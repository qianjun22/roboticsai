import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 40230
SERVICE = "robot_kitting_station"
DESCRIPTION = "Simulation service for kitting station"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>robot_kitting_station</title><style>
body{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;}
.header{background:#C74634;padding:20px 32px;}
h1{margin:0;font-size:24px;color:#fff;}
.subtitle{color:#fecaca;font-size:14px;margin-top:4px;}
.content{padding:32px;}
.metric{background:#1e293b;border-radius:8px;padding:20px;margin:12px 0;}
.bars{display:flex;align-items:flex-end;gap:4px;height:80px;margin-top:16px;}
.bar{width:20px;border-radius:3px 3px 0 0;}
</style></head><body>
<div class="header"><h1>robot_kitting_station</h1><div class="subtitle">Simulation service for kitting station port 40230</div></div>
<div class="content">
<div class="metric"><strong>Status:</strong> operational</div>
<div class="metric"><strong>Port:</strong> 40230</div>
<div class="bars">{bars}</div>
</div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
