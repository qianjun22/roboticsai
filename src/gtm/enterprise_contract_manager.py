from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="Enterprise Contract Manager")

PORT = 9989
TITLE = "Enterprise Contract Manager"
BG = "#0f172a"
ORACLE_RED = "#C74634"
SKY_BLUE = "#38bdf8"

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Contract Manager</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; }
    h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; text-align: center; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 2rem; width: 100%; max-width: 700px; box-shadow: 0 4px 24px rgba(0,0,0,0.4); }
    .bar-chart { display: flex; align-items: flex-end; gap: 10px; height: 180px; margin-top: 1rem; }
    .bar-wrap { display: flex; flex-direction: column; align-items: center; flex: 1; }
    .bar { width: 100%; border-radius: 4px 4px 0 0; background: #38bdf8; transition: height 0.3s; }
    .bar-label { font-size: 0.65rem; color: #94a3b8; margin-top: 4px; }
    .stats { display: flex; gap: 1rem; margin-top: 1.5rem; flex-wrap: wrap; }
    .stat { flex: 1; background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; min-width: 120px; }
    .stat-val { font-size: 1.5rem; font-weight: bold; color: #C74634; }
    .stat-label { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
    .health { margin-top: 1.5rem; text-align: center; }
    .health a { color: #38bdf8; text-decoration: none; font-size: 0.9rem; }
    .health a:hover { text-decoration: underline; }
    .port-badge { display: inline-block; background: #C74634; color: #fff; border-radius: 20px; padding: 2px 14px; font-size: 0.8rem; margin-bottom: 1rem; }
  </style>
</head>
<body>
  <div class="port-badge">PORT 9989</div>
  <h1>Enterprise Contract Manager</h1>
  <div class="subtitle">OCI Robot Cloud &mdash; GTM Service</div>
  <div class="card">
    <div class="bar-chart" id="chart"></div>
    <div class="stats">
      <div class="stat"><div class="stat-val">9989</div><div class="stat-label">Service Port</div></div>
      <div class="stat"><div class="stat-val">OCI</div><div class="stat-label">Platform</div></div>
      <div class="stat"><div class="stat-val">GTM</div><div class="stat-label">Module</div></div>
      <div class="stat"><div class="stat-val">483A</div><div class="stat-label">Cycle</div></div>
    </div>
    <div class="health"><a href="/health">/health</a></div>
  </div>
  <script>
    const bars = [65, 80, 70, 95, 60, 88, 75, 50, 82, 91];
    const labels = ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8','Q9','Q10'];
    const chart = document.getElementById('chart');
    bars.forEach((h, i) => {
      const wrap = document.createElement('div');
      wrap.className = 'bar-wrap';
      const bar = document.createElement('div');
      bar.className = 'bar';
      bar.style.height = h + '%';
      const label = document.createElement('div');
      label.className = 'bar-label';
      label.textContent = labels[i];
      wrap.appendChild(bar);
      wrap.appendChild(label);
      chart.appendChild(wrap);
    });
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML

@app.get("/health")
def health():
    return {"status": "ok", "service": TITLE, "port": PORT}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
