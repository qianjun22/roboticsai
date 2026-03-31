"""
OCI Robot Cloud — Force Torque Impedance Controller V2
FastAPI service — port 11236
Variable impedance control with force-torque feedback and adaptive stiffness
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11236
SERVICE = "force_torque_impedance_controller_v2"
DESCRIPTION = "Variable impedance controller v2 combining force-torque feedback with adaptive stiffness scheduling for compliant manipulation across precision assembly and contact-rich tasks"

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
var d=[500,300,150,80,150,300,500,300,150];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#C74634';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
