import datetime, fastapi, fastapi.responses, uvicorn
PORT = 31182
SERVICE = "robot_raphe_nucleus_v5"
DESCRIPTION = "Robot raphe nucleus simulation service v5"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{font-family:sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:2rem}}.bars{{display:flex;align-items:flex-end;gap:4px;height:120px;margin:1rem 0}}.bar{{width:20px;border-radius:4px 4px 0 0}}</style></head><body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p><div class="bars">{bars}</div><p>Port: {PORT}</p></body></html>"""
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
