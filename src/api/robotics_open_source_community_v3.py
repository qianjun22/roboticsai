import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 17005
SERVICE = "robotics-open-source-community-v3"
DESCRIPTION = "GTM open source community v3 for robotics OSS contributor and dual-license strategy"

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
body{{margin:0;background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}
h1{{color:#38bdf8}}.bars{{display:flex;gap:4px;align-items:flex-end;height:120px;margin-top:1rem}}
.bar{{width:24px;border-radius:4px 4px 0 0}}
</style></head><body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p><div class="bars">{bars}</div></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
