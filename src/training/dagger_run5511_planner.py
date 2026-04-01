import datetime, fastapi, fastapi.responses, uvicorn
PORT = 31604
SERVICE = "dagger_run5511_planner"
DESCRIPTION = "DAgger run 5511 planner service"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{font-family:sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:2rem}}.bars{{display:flex;align-items:flex-end;gap:4px;height:80px}}.bar{{width:18px;border-radius:3px 3px 0 0}}</style></head><body><h2>{SERVICE}</h2><p>Port: {PORT}</p><div class="bars">{bars}</div></body></html>"""
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
