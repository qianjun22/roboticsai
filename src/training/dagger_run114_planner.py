# DAgger Run114 Planner — PORT 9994
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

PORT = 9994
TITLE = "DAgger Run114 Planner"

app = FastAPI(title=TITLE)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    body {{ margin: 0; background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }}
    header {{ background: #C74634; padding: 1.2rem 2rem; }}
    header h1 {{ margin: 0; font-size: 1.6rem; color: #fff; }}
    header span {{ color: #38bdf8; font-size: 0.9rem; }}
    main {{ padding: 2rem; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
    svg text {{ fill: #e2e8f0; font-size: 11px; }}
    .bar {{ fill: #38bdf8; }}
    .bar:hover {{ fill: #C74634; }}
    .axis {{ stroke: #475569; }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <span>PORT {port} &nbsp;|&nbsp; OCI Robot Cloud</span>
  </header>
  <main>
    <div class="card">
      <h2 style="color:#38bdf8;margin-top:0">Run114 Planning Overview</h2>
      <p>DAgger iteration 114 — adaptive query strategy with curriculum-guided demonstration selection.</p>
    </div>
    <div class="card">
      <h2 style="color:#38bdf8;margin-top:0">Episode Reward per Rollout</h2>
      <svg width="100%" viewBox="0 0 520 180" xmlns="http://www.w3.org/2000/svg">
        <line x1="40" y1="10" x2="40" y2="150" class="axis" stroke-width="1"/>
        <line x1="40" y1="150" x2="510" y2="150" class="axis" stroke-width="1"/>
        <!-- 10 bars -->
        <rect class="bar" x="55"  y="90"  width="35" height="60"/>
        <rect class="bar" x="101" y="75"  width="35" height="75"/>
        <rect class="bar" x="147" y="60"  width="35" height="90"/>
        <rect class="bar" x="193" y="50"  width="35" height="100"/>
        <rect class="bar" x="239" y="40"  width="35" height="110"/>
        <rect class="bar" x="285" y="30"  width="35" height="120"/>
        <rect class="bar" x="331" y="25"  width="35" height="125"/>
        <rect class="bar" x="377" y="20"  width="35" height="130"/>
        <rect class="bar" x="423" y="15"  width="35" height="135"/>
        <rect class="bar" x="469" y="10"  width="35" height="140"/>
        <!-- x labels -->
        <text x="72"  y="165">R1</text>
        <text x="118" y="165">R2</text>
        <text x="164" y="165">R3</text>
        <text x="210" y="165">R4</text>
        <text x="256" y="165">R5</text>
        <text x="302" y="165">R6</text>
        <text x="348" y="165">R7</text>
        <text x="394" y="165">R8</text>
        <text x="440" y="165">R9</text>
        <text x="480" y="165">R10</text>
      </svg>
    </div>
  </main>
</body>
</html>
""".format(title=TITLE, port=PORT)


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


@app.get("/health")
async def health():
    return {"status": "ok", "service": TITLE, "port": PORT}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
