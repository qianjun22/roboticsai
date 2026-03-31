import datetime
import fastapi
import fastapi.responses
import uvicorn

PORT = 13311
SERVICE = "robotics_pricing_elasticity_model"
DESCRIPTION = "Pricing elasticity model for measuring demand sensitivity to price changes across robotics cloud tiers and fleet sizes"

app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=fastapi.responses.HTMLResponse)
def dashboard():
    bars = "".join(f'<div class="bar" style="height:{10+i*7}%;background:#38bdf8;opacity:{0.5+i*0.07:.2f}"></div>' for i in range(8))
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:2rem}}
h1{{color:#C74634;font-size:1.5rem}}p{{color:#94a3b8}}.chart{{display:flex;align-items:flex-end;gap:4px;height:80px;margin-top:1rem}}.bar{{width:24px;border-radius:3px 3px 0 0}}</style></head>
<body><h1>{SERVICE}</h1><p>{DESCRIPTION}</p><p>Port: {PORT}</p><div class="chart">{bars}</div>
<script>setInterval(()=>document.querySelectorAll('.bar').forEach(b=>b.style.height=Math.random()*80+10+'%'),1200)</script>
</body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
