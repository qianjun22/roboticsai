"""
OCI Robot Cloud — Revenue Leakage Detector
FastAPI service — port 11275
Detect and recover revenue leakage from billing gaps, discount abuse, and renewal slippage
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11275
SERVICE = "revenue_leakage_detector"
DESCRIPTION = "Revenue leakage detector identifying and recovering lost revenue from billing gaps, unauthorized discounts, renewal slippage, and unapplied contract terms"

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
var d=[8.2,6.1,4.8,3.9,3.1,2.5,2.0,1.6,1.2];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#38bdf8';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
