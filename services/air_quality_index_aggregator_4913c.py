import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 27673
SERVICE = "air_quality_index_aggregator_4913c"
DESCRIPTION = "Aggregates air quality indices from environmental robots"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title><style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;}}.header{{background:#C74634;padding:20px 32px;}}h1{{margin:0;font-size:24px;color:#fff;}}.sub{{color:#fca5a5;font-size:13px;}}.content{{padding:32px;}}.metric{{background:#1e293b;border-radius:12px;padding:20px;}}.bars{{display:flex;gap:4px;align-items:flex-end;height:60px;}}.bar{{width:20px;border-radius:4px 4px 0 0;}}</style></head><body><div class="header"><h1>{SERVICE}</h1><div class="sub">{DESCRIPTION}</div></div><div class="content"><div class="metric"><b>Port:</b> {PORT} | <b>Status:</b> <span style="color:#4ade80">&#9679; Live</span><div class="bars">{bars}</div></div></div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
