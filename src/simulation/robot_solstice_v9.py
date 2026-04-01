import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 32506
SERVICE = "robot_solstice_v9"
DESCRIPTION = "Solstice and equinox event robot operational planning service"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{font-family:sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:2rem}}.bars{{display:flex;gap:4px;align-items:flex-end;height:80px}}.bar{{width:20px;border-radius:2px 2px 0 0}}</style></head><body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p><p>Port: {PORT}</p><div class="bars">{bars}</div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
