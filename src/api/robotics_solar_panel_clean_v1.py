import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 22823
SERVICE = "robotics_solar_panel_clean_v1"
DESCRIPTION = "Solar panel cleaning robotics API v1 — dust accumulation modeling and waterless wipe cycles"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;font-family:sans-serif;background:#0f172a;color:#e2e8f0}}header{{background:#C74634;padding:16px 24px}}h1{{margin:0;font-size:1.4rem}}.dash{{display:flex;gap:12px;padding:24px;align-items:flex-end;height:160px}}.bar{{width:40px;border-radius:4px 4px 0 0;transition:height .3s}}.info{{padding:0 24px;color:#94a3b8}}</style></head><body><header><h1>OCI Robot Cloud — {SERVICE}</h1></header><div class="dash">{bars}</div><div class="info"><p>Port: {PORT} | {DESCRIPTION}</p></div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
