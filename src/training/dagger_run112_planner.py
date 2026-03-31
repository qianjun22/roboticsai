"""DAgger Run112 Planner — cycle-482B (port 9986)"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

PORT = 9986
TITLE = "DAgger Run112 Planner"

app = FastAPI(title=TITLE)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
      padding: 2rem;
    }}
    h1 {{ color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }}
    .subtitle {{ color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 2rem;
      width: 100%;
      max-width: 720px;
    }}
    svg {{ width: 100%; height: 220px; }}
    .bar {{ fill: #38bdf8; transition: opacity 0.2s; }}
    .bar:hover {{ opacity: 0.75; }}
    .axis-label {{ fill: #94a3b8; font-size: 11px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem;
      margin-top: 1.5rem;
    }}
    .stat {{
      background: #0f172a;
      border-radius: 8px;
      padding: 1rem;
      text-align: center;
    }}
    .stat-val {{ color: #C74634; font-size: 1.5rem; font-weight: 700; }}
    .stat-lbl {{ color: #64748b; font-size: 0.75rem; margin-top: 0.25rem; }}
    .port {{ color: #475569; font-size: 0.8rem; margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="subtitle">OCI Robot Cloud · cycle-482B</div>
  <div class="card">
    <svg viewBox="0 0 640 220" xmlns="http://www.w3.org/2000/svg">
      <!-- 10 bars representing DAgger iteration metrics -->
      <rect class="bar" x="20"  y="60"  width="46" height="140" rx="4"/>
      <rect class="bar" x="84"  y="40"  width="46" height="160" rx="4"/>
      <rect class="bar" x="148" y="80"  width="46" height="120" rx="4"/>
      <rect class="bar" x="212" y="30"  width="46" height="170" rx="4"/>
      <rect class="bar" x="276" y="50"  width="46" height="150" rx="4"/>
      <rect class="bar" x="340" y="20"  width="46" height="180" rx="4"/>
      <rect class="bar" x="404" y="70"  width="46" height="130" rx="4"/>
      <rect class="bar" x="468" y="45"  width="46" height="155" rx="4"/>
      <rect class="bar" x="532" y="35"  width="46" height="165" rx="4"/>
      <rect class="bar" x="596" y="55"  width="46" height="145" rx="4"/>
      <!-- X-axis labels -->
      <text class="axis-label" x="43"  y="215" text-anchor="middle">i1</text>
      <text class="axis-label" x="107" y="215" text-anchor="middle">i2</text>
      <text class="axis-label" x="171" y="215" text-anchor="middle">i3</text>
      <text class="axis-label" x="235" y="215" text-anchor="middle">i4</text>
      <text class="axis-label" x="299" y="215" text-anchor="middle">i5</text>
      <text class="axis-label" x="363" y="215" text-anchor="middle">i6</text>
      <text class="axis-label" x="427" y="215" text-anchor="middle">i7</text>
      <text class="axis-label" x="491" y="215" text-anchor="middle">i8</text>
      <text class="axis-label" x="555" y="215" text-anchor="middle">i9</text>
      <text class="axis-label" x="619" y="215" text-anchor="middle">i10</text>
    </svg>
    <div class="stats">
      <div class="stat">
        <div class="stat-val">112</div>
        <div class="stat-lbl">DAgger Run</div>
      </div>
      <div class="stat">
        <div class="stat-val">9986</div>
        <div class="stat-lbl">Port</div>
      </div>
      <div class="stat">
        <div class="stat-val">482B</div>
        <div class="stat-lbl">Cycle</div>
      </div>
    </div>
  </div>
  <div class="port">Listening on port {port}</div>
</body>
</html>
""".format(title=TITLE, port=PORT)


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


@app.get("/health")
async def health():
    return {"status": "ok", "service": TITLE, "port": PORT, "cycle": "482B"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
