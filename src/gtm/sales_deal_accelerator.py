"""
OCI Robot Cloud — Sales Deal Accelerator
FastAPI service — port 11215
Compress enterprise sales cycles from 4.2 months to 2.5 months
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11215
SERVICE = "sales_deal_accelerator"
DESCRIPTION = "Sales deal acceleration platform providing playbooks, proof points, and champion enablement to compress enterprise sales cycles from 4.2 months toward 2.5 months"

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
var d=[4.2,3.9,3.6,3.3,3.1,2.9,2.7,2.6,2.5];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#38bdf8';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
