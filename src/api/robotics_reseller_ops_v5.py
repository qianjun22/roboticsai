import datetime, fastapi, fastapi.responses, uvicorn
PORT = 30175
SERVICE = "robotics_reseller_ops_v5"
DESCRIPTION = "Robotics reseller ops v5 GTM service"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;}}.header{{background:#C74634;padding:20px 32px;}}.bars{{display:flex;gap:6px;align-items:flex-end;height:80px;padding:16px 32px;}}.bar{{width:18px;border-radius:3px 3px 0 0;}}</style></head><body><div class="header"><h2>{SERVICE}</h2><p>{DESCRIPTION}</p></div><div class="bars">{bars}</div><p style="padding:0 32px">Port: {PORT}</p></body></html>"""
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
