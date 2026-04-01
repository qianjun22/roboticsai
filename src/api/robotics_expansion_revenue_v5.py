import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 15681
SERVICE = "robotics_expansion_revenue_v5"
DESCRIPTION = "Expansion revenue v5: upsell and cross-sell opportunity scoring for robot platform accounts"

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
    body{{font-family:sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:2rem}}
    h1{{color:#38bdf8}}p{{color:#94a3b8}}
    .chart{{display:flex;align-items:flex-end;gap:4px;height:80px;margin-top:1rem}}
    .bar{{width:20px;border-radius:3px 3px 0 0}}
    </style></head><body>
    <h1>{SERVICE}</h1><p>{DESCRIPTION}</p><p>Port: {PORT}</p>
    <div class="chart">{bars}</div>
    </body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
