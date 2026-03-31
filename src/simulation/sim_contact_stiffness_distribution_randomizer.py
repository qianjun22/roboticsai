"""
OCI Robot Cloud — Sim Contact Stiffness Distribution Randomizer
FastAPI service — port 11256
Contact stiffness distribution randomization for robust contact-rich manipulation
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11256
SERVICE = "sim_contact_stiffness_distribution_randomizer"
DESCRIPTION = "Contact stiffness distribution randomization varying surface compliance, contact spring constants, and damping ratios to train policies robust to diverse material properties"

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
var d=[1e2,5e2,1e3,5e3,1e4,5e4,1e4,5e3,1e3];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#C74634';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
