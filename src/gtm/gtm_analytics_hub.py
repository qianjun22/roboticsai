"""
OCI Robot Cloud — GTM Analytics Hub
FastAPI service — port 11277
Unified GTM analytics: pipeline, CAC, LTV, funnel, and cohort insights in one dashboard
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11277
SERVICE = "gtm_analytics_hub"
DESCRIPTION = "Unified GTM analytics hub consolidating pipeline analytics, CAC by channel, LTV cohorts, funnel conversion, and revenue forecasting into a single executive dashboard"

app = FastAPI(title=SERVICE, version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return f"""<!DOCTYPE html><html><head><title>{SERVICE}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:2rem}}
h1{{color:#C74634}}canvas{{background:#1e293b;border-radius:8px}}</style></head>
<body><h1>{SERVICE}</h1><p style="color:#38bdf8">Port {PORT} — {DESCRIPTION}</p>
<canvas id="c" width="400" height="120"></canvas>
<script>
var c=document.getElementById('c').getContext('2d');
var d=[12,18,24,31,39,48,57,67,78];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#38bdf8';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
