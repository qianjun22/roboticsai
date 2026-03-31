"""
OCI Robot Cloud — Sim Friction Coefficient Randomizer
FastAPI service — port 11264
Surface friction coefficient randomization for robust grasping and locomotion
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11264
SERVICE = "sim_friction_coefficient_randomizer"
DESCRIPTION = "Surface friction coefficient randomization varying static/dynamic friction and rolling resistance across object surfaces to train policies robust to diverse material interactions"

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
var d=[0.1,0.3,0.5,0.7,1.0,1.4,1.8,1.0,0.5];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#C74634';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
