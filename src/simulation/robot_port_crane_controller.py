import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 17778
SERVICE = "robot_port_crane_controller"
DESCRIPTION = "Autonomous controller for port gantry cranes and container handling"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;font-family:sans-serif;background:#0f172a;color:#e2e8f0}}header{{background:#C74634;padding:1rem 2rem}}h1{{margin:0;font-size:1.4rem}}.cards{{display:flex;gap:1rem;padding:2rem;flex-wrap:wrap}}.card{{background:#1e293b;border-radius:8px;padding:1.5rem;min-width:180px}}.val{{font-size:2rem;font-weight:bold;color:#38bdf8}}.chart{{display:flex;align-items:flex-end;gap:4px;height:80px;padding:1rem 2rem}}.bar{{width:28px;border-radius:4px 4px 0 0}}</style></head><body><header><h1>{SERVICE} — port {PORT}</h1></header><div class="cards"><div class="card"><div>Status</div><div class="val">OK</div></div><div class="card"><div>Port</div><div class="val">{PORT}</div></div><div class="card"><div>Uptime</div><div class="val">99.9%</div></div></div><div class="chart">{bars}</div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
