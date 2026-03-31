import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 15078
SERVICE = "robot_tunnel_lining_inspector"
DESCRIPTION = "Tunnel lining inspection robot for detecting cracks and structural defects"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(
        f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>'
        for i in range(8)
    )
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>
    body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;}}
    h1{{font-size:1.5rem;margin-bottom:0.5rem;}}p{{color:#94a3b8;margin:0.25rem 0;}}
    .chart{{display:flex;align-items:flex-end;gap:4px;height:80px;margin-top:1rem;}}
    .bar{{width:18px;border-radius:3px 3px 0 0;}}
    </style></head><body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p><p>Port: {PORT}</p>
    <div class="chart">{bars}</div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
