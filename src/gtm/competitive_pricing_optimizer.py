"""Competitive Pricing Optimizer — cycle-482B (port 9987)"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

PORT = 9987
TITLE = "Competitive Pricing Optimizer"

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
    .bar {{ fill: #C74634; transition: opacity 0.2s; }}
    .bar:hover {{ opacity: 0.75; }}
    .bar-accent {{ fill: #38bdf8; }}
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
    .stat-val {{ color: #38bdf8; font-size: 1.5rem; font-weight: 700; }}
    .stat-lbl {{ color: #64748b; font-size: 0.75rem; margin-top: 0.25rem; }}
    .port {{ color: #475569; font-size: 0.8rem; margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="subtitle">OCI Robot Cloud · cycle-482B</div>
  <div class="card">
    <svg viewBox="0 0 640 220" xmlns="http://www.w3.org/2000/svg">
      <!-- 10 bars representing pricing tier competitiveness scores -->
      <rect class="bar" x="20"  y="50"  width="46" height="150" rx="4"/>
      <rect class="bar bar-accent" x="84"  y="70"  width="46" height="130" rx="4"/>
      <rect class="bar" x="148" y="30"  width="46" height="170" rx="4"/>
      <rect class="bar bar-accent" x="212" y="90"  width="46" height="110" rx="4"/>
      <rect class="bar" x="276" y="20"  width="46" height="180" rx="4"/>
      <rect class="bar bar-accent" x="340" y="60"  width="46" height="140" rx="4"/>
      <rect class="bar" x="404" y="40"  width="46" height="160" rx="4"/>
      <rect class="bar bar-accent" x="468" y="80"  width="46" height="120" rx="4"/>
      <rect class="bar" x="532" y="25"  width="46" height="175" rx="4"/>
      <rect class="bar bar-accent" x="596" y="55"  width="46" height="145" rx="4"/>
      <!-- X-axis labels -->
      <text class="axis-label" x="43"  y="215" text-anchor="middle">T1</text>
      <text class="axis-label" x="107" y="215" text-anchor="middle">T2</text>
      <text class="axis-label" x="171" y="215" text-anchor="middle">T3</text>
      <text class="axis-label" x="235" y="215" text-anchor="middle">T4</text>
      <text class="axis-label" x="299" y="215" text-anchor="middle">T5</text>
      <text class="axis-label" x="363" y="215" text-anchor="middle">T6</text>
      <text class="axis-label" x="427" y="215" text-anchor="middle">T7</text>
      <text class="axis-label" x="491" y="215" text-anchor="middle">T8</text>
      <text class="axis-label" x="555" y="215" text-anchor="middle">T9</text>
      <text class="axis-label" x="619" y="215" text-anchor="middle">T10</text>
    </svg>
    <div class="stats">
      <div class="stat">
        <div class="stat-val">10</div>
        <div class="stat-lbl">Price Tiers</div>
      </div>
      <div class="stat">
        <div class="stat-val">9987</div>
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
