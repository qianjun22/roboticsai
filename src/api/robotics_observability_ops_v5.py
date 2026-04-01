import datetime, fastapi, fastapi.responses, uvicorn
PORT = 31015
SERVICE = "robotics_observability_ops"
DESCRIPTION = "Robotics observability operations service"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{font-family:sans-serif;background:#0f172a;color:#f1f5f9;margin:0;padding:32px}}.bars{{display:flex;gap:8px;align-items:flex-end;height:120px;margin:24px 0}}.bar{{width:32px;border-radius:4px 4px 0 0}}</style></head><body><h1>{SERVICE}</h1><p>Port: {PORT}</p><div class="bars">{bars}</div></body></html>"""
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
