import datetime, fastapi, fastapi.responses, uvicorn
PORT = 30905
SERVICE = "robotics_sales_enablement"
DESCRIPTION = "Robotics sales enablement service"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;background:#0f172a;color:#f1f5f9;font-family:sans-serif}}.header{{background:#1e293b;padding:24px 32px}}.bars{{display:flex;align-items:flex-end;gap:6px;height:120px;padding:16px 32px}}.bar{{width:32px;border-radius:4px 4px 0 0}}</style></head><body><div class="header"><h1>{SERVICE}</h1><p>{DESCRIPTION}</p></div><div class="bars">{bars}</div><p style="padding:0 32px">Port: {PORT}</p></body></html>"""
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
