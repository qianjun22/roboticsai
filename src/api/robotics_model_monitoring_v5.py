import datetime, fastapi, fastapi.responses, uvicorn
PORT = 30735
SERVICE = "robotics_model_monitoring_v5"
DESCRIPTION = "Model monitoring GTM microservice for robotics inference performance tracking and data drift detection"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;font-family:sans-serif;background:#0f172a;color:#e2e8f0}}header{{background:#1e293b;padding:24px 32px}}h1{{margin:0;font-size:1.4rem;color:#38bdf8}}.bars{{display:flex;align-items:flex-end;gap:6px;height:120px;padding:32px}}.bar{{width:28px;border-radius:4px 4px 0 0}}</style></head><body><header><h1>{SERVICE}</h1><p style="margin:4px 0 0;color:#94a3b8">{DESCRIPTION}</p></header><div class="bars">{bars}</div><p style="padding:0 32px">Port: {PORT}</p></body></html>"""
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
