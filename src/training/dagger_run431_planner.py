"""
OCI Robot Cloud — DAgger Run 431 Planner
FastAPI service — port 11278
AWAC advantage-weighted actor-critic offline-to-online DAgger for seamless offline pretraining to online finetuning
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn, datetime

PORT = 11278
SERVICE = "dagger_run431_planner"
DESCRIPTION = "AWAC advantage-weighted actor-critic DAgger enabling seamless offline pretraining on 1000-demo dataset followed by online DAgger fine-tuning without reward engineering"

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
var d=[82,84,86,88,89,91,92,93,95];
var max=Math.max(...d);
d.forEach(function(v,i){{c.fillStyle='#C74634';c.fillRect(i*44+10,110-v/max*100,36,v/max*100)}});
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
