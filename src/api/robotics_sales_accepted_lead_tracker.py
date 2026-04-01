import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 41027
SERVICE = "robotics_sales_accepted_lead_tracker"
DESCRIPTION = "Sales accepted lead tracker for robotics GTM analytics"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;font-family:sans-serif;background:#0f172a;color:#e2e8f0}}header{{background:#C74634;padding:16px 24px}}h1{{margin:0;font-size:1.4rem}}.cards{{display:flex;gap:16px;padding:24px;flex-wrap:wrap}}.card{{background:#1e293b;border-radius:8px;padding:20px;min-width:200px}}.chart{{display:flex;align-items:flex-end;gap:4px;height:80px;margin-top:12px}}.bar{{width:20px;border-radius:3px 3px 0 0}}</style></head><body><header><h1>OCI Robot Cloud — {SERVICE}</h1></header><div class="cards"><div class="card"><div>Port</div><div style="font-size:2rem;color:#38bdf8">{PORT}</div></div><div class="card"><div>Status</div><div style="color:#4ade80">Running</div><div class="chart">{bars}</div></div><div class="card"><div>Description</div><div style="color:#94a3b8">{DESCRIPTION}</div></div></div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
