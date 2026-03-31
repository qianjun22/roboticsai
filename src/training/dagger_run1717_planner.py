import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 16428
SERVICE = "dagger_run1717_planner"
DESCRIPTION = "DAgger run 1717 training planner for iterative policy improvement"

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
body{{margin:0;background:#0f172a;color:#f1f5f9;font-family:system-ui;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh}}
h1{{color:#C74634;font-size:2rem;margin-bottom:0.5rem}}
p{{color:#94a3b8;margin-bottom:2rem}}
.bars{{display:flex;gap:4px;align-items:flex-end;height:80px}}
.bar{{width:20px;border-radius:4px 4px 0 0}}
</style></head><body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p><div class="bars">{bars}</div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
