# Series A Pipeline Tracker — PORT 9995
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

PORT = 9995
TITLE = "Series A Pipeline Tracker"

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
      <h2 style="color:#38bdf8;margin-top:0">Series A Fundraise Overview</h2>
      <p>Tracks prospect pipeline, commitment velocity, and close probability across Series A investor outreach.</p>
    </div>
    <div class="card">
      <h2 style="color:#38bdf8;margin-top:0">Commitment Progress by Investor Stage</h2>
      <svg width="100%" viewBox="0 0 520 180" xmlns="http://www.w3.org/2000/svg">
        <line x1="40" y1="10" x2="40" y2="150" class="axis" stroke-width="1"/>
        <line x1="40" y1="150" x2="510" y2="150" class="axis" stroke-width="1"/>
        <!-- 10 bars -->
        <rect class="bar" x="55"  y="30"  width="35" height="120"/>
        <rect class="bar" x="101" y="50"  width="35" height="100"/>
        <rect class="bar" x="147" y="70"  width="35" height="80"/>
        <rect class="bar" x="193" y="55"  width="35" height="95"/>
        <rect class="bar" x="239" y="40"  width="35" height="110"/>
        <rect class="bar" x="285" y="80"  width="35" height="70"/>
        <rect class="bar" x="331" y="35"  width="35" height="115"/>
        <rect class="bar" x="377" y="60"  width="35" height="90"/>
        <rect class="bar" x="423" y="45"  width="35" height="105"/>
        <rect class="bar" x="469" y="20"  width="35" height="130"/>
        <!-- x labels -->
        <text x="62"  y="165">Aware</text>
        <text x="104" y="165">Intro</text>
        <text x="150" y="165">DD</text>
        <text x="193" y="165">Term</text>
        <text x="239" y="165">Legal</text>
        <text x="285" y="165">Sign</text>
        <text x="331" y="165">Wire</text>
        <text x="377" y="165">Close</text>
        <text x="420" y="165">Follow</text>
        <text x="466" y="165">Done</text>
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
