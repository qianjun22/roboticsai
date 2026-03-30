"""Financial Model V3 — port 8981
3-year P&L (base/bull/bear), break-even at $380k ARR = Q3 2027 base / Q1 2027 bull
Burn $52k/mo, 18-month runway post $4M raise, headcount 3→8→18 FTE
"""

import math
import random
import json

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Financial Model V3</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 24px 0 12px; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
  .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
  .card .value { font-size: 1.75rem; font-weight: 700; }
  .card .sub { font-size: 0.82rem; color: #64748b; margin-top: 4px; }
  .chart-wrap { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; margin-bottom: 24px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #0f172a; color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; padding: 10px 14px; text-align: right; }
  th:first-child { text-align: left; }
  td { padding: 10px 14px; border-bottom: 1px solid #1e293b; font-size: 0.88rem; text-align: right; }
  td:first-child { text-align: left; font-weight: 600; }
  tr:hover td { background: #1e293b; }
  .positive { color: #4ade80; } .negative { color: #f87171; } .neutral { color: #94a3b8; }
  .scenario-base { color: #38bdf8; } .scenario-bull { color: #4ade80; } .scenario-bear { color: #f87171; }
</style>
</head>
<body>
<h1>Financial Model V3</h1>
<p class="subtitle">3-Year P&amp;L Scenarios — OCI Robot Cloud Business Case</p>

<div class="grid">
  <div class="card">
    <div class="label">Break-Even ARR</div>
    <div class="value" style="color:#4ade80">$380k</div>
    <div class="sub">Q3 2027 base &bull; Q1 2027 bull</div>
  </div>
  <div class="card">
    <div class="label">Monthly Burn</div>
    <div class="value" style="color:#f87171">$52k</div>
    <div class="sub">Pre-revenue run rate</div>
  </div>
  <div class="card">
    <div class="label">Runway (post $4M raise)</div>
    <div class="value" style="color:#38bdf8">18 mo</div>
    <div class="sub">$4M / $52k burn &#x2248; 18 months</div>
  </div>
  <div class="card">
    <div class="label">Headcount</div>
    <div class="value" style="color:#fbbf24">3→8→18</div>
    <div class="sub">Y1 → Y2 → Y3 FTE</div>
  </div>
  <div class="card">
    <div class="label">Y3 ARR (Base)</div>
    <div class="value" style="color:#38bdf8">$3.2M</div>
    <div class="sub">~8 enterprise customers @ $400k</div>
  </div>
  <div class="card">
    <div class="label">Y3 ARR (Bull)</div>
    <div class="value" style="color:#4ade80">$6.8M</div>
    <div class="sub">~17 customers, faster adoption</div>
  </div>
</div>

<h2>Scenario P&amp;L Chart (Quarterly)</h2>
<div class="chart-wrap">
  <svg id="pnl" width="100%" viewBox="0 0 760 340" xmlns="http://www.w3.org/2000/svg"></svg>
</div>

<h2>3-Year P&amp;L Summary by Scenario</h2>
<div class="card">
<table>
  <thead>
    <tr>
      <th>Metric</th>
      <th class="scenario-bear">Bear</th>
      <th class="scenario-base">Base</th>
      <th class="scenario-bull">Bull</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>Y1 ARR</td><td class="scenario-bear">$180k</td><td class="scenario-base">$320k</td><td class="scenario-bull">$520k</td></tr>
    <tr><td>Y2 ARR</td><td class="scenario-bear">$680k</td><td class="scenario-base">$1.4M</td><td class="scenario-bull">$2.8M</td></tr>
    <tr><td>Y3 ARR</td><td class="scenario-bear">$1.4M</td><td class="scenario-base">$3.2M</td><td class="scenario-bull">$6.8M</td></tr>
    <tr><td>Break-Even Quarter</td><td class="scenario-bear">Q1 2028</td><td class="scenario-base">Q3 2027</td><td class="scenario-bull">Q1 2027</td></tr>
    <tr><td>Y3 Gross Margin</td><td class="scenario-bear">48%</td><td class="scenario-base">62%</td><td class="scenario-bull">71%</td></tr>
    <tr><td>Y3 Net Margin</td><td class="scenario-bear">-18%</td><td class="scenario-base">+8%</td><td class="scenario-bull">+24%</td></tr>
    <tr><td>Total Raise Needed</td><td class="scenario-bear">$8M</td><td class="scenario-base">$4M</td><td class="scenario-bull">$4M</td></tr>
  </tbody>
</table>
</div>

<h2>Unit Economics Evolution</h2>
<div class="chart-wrap">
  <svg id="uniteco" width="100%" viewBox="0 0 760 280" xmlns="http://www.w3.org/2000/svg"></svg>
</div>

<script>
// --- P&L Scenario Chart ---
(function() {
  const svg = document.getElementById('pnl');
  const W=760,H=340,padL=72,padR=30,padT=36,padB=56;
  const iW=W-padL-padR, iH=H-padT-padB;

  // Quarterly ARR ($k), 12 quarters Q1-2026 to Q4-2028
  const quarters = ['Q1\'26','Q2\'26','Q3\'26','Q4\'26','Q1\'27','Q2\'27','Q3\'27','Q4\'27','Q1\'28','Q2\'28','Q3\'28','Q4\'28'];
  const bear = [20,  40,  70,  110, 160, 220, 300, 400,  520,  680,  880,  1100];
  const base = [40,  80,  130, 200, 280, 380, 520, 720,  980,  1300, 1750, 2300];
  const bull = [80,  150, 250, 380, 540, 760, 1050,1420, 1880, 2480, 3200, 4200];
  // Burn (costs) $k/quarter
  const burn = [156, 156, 168, 180, 204, 228, 264, 312,  372,  432,  504,  576];

  const minY = -500, maxY = 4500;
  function sx(i) { return padL + (i/(quarters.length-1))*iW; }
  function sy(v) { return padT + (1-(v-minY)/(maxY-minY))*iH; }

  function el(tag,attrs) {
    const e=document.createElementNS('http://www.w3.org/2000/svg',tag);
    Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));
    return e;
  }

  // Zero line
  svg.appendChild(el('line',{x1:padL,y1:sy(0),x2:padL+iW,y2:sy(0),stroke:'#475569','stroke-width':1,'stroke-dasharray':'4,3'}));
  // Grid
  [0,500,1000,2000,3000,4000].forEach(v=>{
    svg.appendChild(el('line',{x1:padL,y1:sy(v),x2:padL+iW,y2:sy(v),stroke:'#1e293b','stroke-width':1}));
    const t=el('text',{x:padL-6,y:sy(v)+4,'text-anchor':'end',fill:'#475569','font-size':11});
    t.textContent=(v>=1000?(v/1000).toFixed(0)+'M':'$'+v+'k'); svg.appendChild(t);
  });
  // Axes
  svg.appendChild(el('line',{x1:padL,y1:padT,x2:padL,y2:padT+iH,stroke:'#475569','stroke-width':1.5}));
  svg.appendChild(el('line',{x1:padL,y1:padT+iH,x2:padL+iW,y2:padT+iH,stroke:'#475569','stroke-width':1.5}));

  // Quarter labels
  quarters.forEach((q,i)=>{
    if(i%2===0) {
      const t=el('text',{x:sx(i),y:padT+iH+18,'text-anchor':'middle',fill:'#475569','font-size':10});
      t.textContent=q; svg.appendChild(t);
    }
  });

  function polyline(data, color, dashed) {
    const pts = data.map((v,i)=>sx(i).toFixed(1)+','+sy(v).toFixed(1)).join(' ');
    const p=el('polyline',{points:pts,fill:'none',stroke:color,'stroke-width':'2.2'});
    if(dashed) p.setAttribute('stroke-dasharray','7,4');
    svg.appendChild(p);
    data.forEach((v,i)=>{
      svg.appendChild(el('circle',{cx:sx(i).toFixed(1),cy:sy(v).toFixed(1),r:3.5,fill:color}));
    });
  }

  // Burn (cost) area
  const burnPts = burn.map((v,i)=>sx(i).toFixed(1)+','+sy(-v).toFixed(1));
  const areaD = 'M'+sx(0)+','+sy(0)+' '+burnPts.join(' ')+' L'+sx(11)+','+sy(0)+' Z';
  const area=el('path',{d:areaD,fill:'#f87171','fill-opacity':'0.07',stroke:'none'});
  svg.appendChild(area);
  polyline(burn.map(v=>-v), '#f87171', true);

  polyline(bear, '#f87171', false);
  polyline(base, '#38bdf8', false);
  polyline(bull, '#4ade80', false);

  // Break-even markers
  function beMarker(qi, color, label) {
    const x=sx(qi), y1=padT, y2=padT+iH;
    svg.appendChild(el('line',{x1:x,y1:y1,x2:x,y2:y2,stroke:color,'stroke-width':1.5,'stroke-dasharray':'5,3','opacity':'0.7'}));
    const t=el('text',{x:x+4,y:padT+16,fill:color,'font-size':10});
    t.textContent=label; svg.appendChild(t);
  }
  beMarker(4, '#4ade80', 'Break-even Bull');
  beMarker(6, '#38bdf8', 'Break-even Base');
  beMarker(8, '#f87171', 'Break-even Bear');

  // Legend
  function leg(x,y,color,dashed,label){
    svg.appendChild(el('line',{x1:x,y1:y,x2:x+24,y2:y,stroke:color,'stroke-width':2.2,...(dashed?{'stroke-dasharray':'7,4'}:{})}));
    const t=el('text',{x:x+30,y:y+4,fill:'#e2e8f0','font-size':12});
    t.textContent=label; svg.appendChild(t);
  }
  leg(padL+10, padT+8, '#4ade80', false, 'Bull ARR');
  leg(padL+130, padT+8, '#38bdf8', false, 'Base ARR');
  leg(padL+250, padT+8, '#f87171', false, 'Bear ARR');
  leg(padL+370, padT+8, '#f87171', true,  'Burn (costs)');
})();

// --- Unit Economics Evolution ---
(function() {
  const svg = document.getElementById('uniteco');
  const W=760,H=280,padL=60,padR=30,padT=30,padB=50;
  const iW=W-padL-padR, iH=H-padT-padB;

  const years = ['Y1 (2026)', 'Y2 (2027)', 'Y3 (2028)'];
  const cac   = [48000, 32000, 22000]; // $ per customer
  const ltv   = [120000, 280000, 520000];
  const ltvCac= ltv.map((v,i) => v/cac[i]);
  const gm    = [0.42, 0.62, 0.68]; // gross margin

  const maxY = 580000, minY = 0;
  function sx(i) { return padL + (i/2)*iW; }
  function sy(v) { return padT + (1-v/maxY)*iH; }

  function el(tag,attrs) {
    const e=document.createElementNS('http://www.w3.org/2000/svg',tag);
    Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));
    return e;
  }

  // Grid
  [0,100000,200000,300000,400000,500000].forEach(v=>{
    svg.appendChild(el('line',{x1:padL,y1:sy(v),x2:padL+iW,y2:sy(v),stroke:'#1e293b','stroke-width':1}));
    const label = v>=1000?'$'+(v/1000)+'k':v===0?'$0':'';
    const t=el('text',{x:padL-6,y:sy(v)+4,'text-anchor':'end',fill:'#475569','font-size':10});
    t.textContent=label; svg.appendChild(t);
  });
  svg.appendChild(el('line',{x1:padL,y1:padT,x2:padL,y2:padT+iH,stroke:'#475569','stroke-width':1.5}));
  svg.appendChild(el('line',{x1:padL,y1:padT+iH,x2:padL+iW,y2:padT+iH,stroke:'#475569','stroke-width':1.5}));

  // Year labels
  years.forEach((y,i)=>{
    const t=el('text',{x:sx(i),y:padT+iH+18,'text-anchor':'middle',fill:'#94a3b8','font-size':12});
    t.textContent=y; svg.appendChild(t);
  });

  // Bars for CAC and LTV
  const barW = 32;
  cac.forEach((v,i)=>{
    const x=sx(i)-barW-4, y=sy(v), h=padT+iH-sy(v);
    svg.appendChild(el('rect',{x,y,width:barW,height:h,fill:'#f87171','fill-opacity':'0.8',rx:3}));
    const t=el('text',{x:x+barW/2,y:y-5,'text-anchor':'middle',fill:'#f87171','font-size':10});
    t.textContent='$'+(v/1000)+'k CAC'; svg.appendChild(t);
  });
  ltv.forEach((v,i)=>{
    const x=sx(i)+4, y=sy(v), h=padT+iH-sy(v);
    svg.appendChild(el('rect',{x,y,width:barW,height:h,fill:'#4ade80','fill-opacity':'0.8',rx:3}));
    const t=el('text',{x:x+barW/2,y:y-5,'text-anchor':'middle',fill:'#4ade80','font-size':10});
    t.textContent='$'+(v/1000)+'k LTV'; svg.appendChild(t);
  });

  // LTV:CAC ratio labels
  ltvCac.forEach((v,i)=>{
    const t=el('text',{x:sx(i),y:padT+iH+36,'text-anchor':'middle',fill:'#fbbf24','font-size':11,'font-weight':'bold'});
    t.textContent='LTV:CAC '+v.toFixed(1)+'x'; svg.appendChild(t);
  });

  // GM line (secondary axis — scaled)
  const gmPts = gm.map((v,i)=>sx(i).toFixed(1)+','+sy(v*maxY).toFixed(1)).join(' ');
  svg.appendChild(el('polyline',{points:gmPts,fill:'none',stroke:'#38bdf8','stroke-width':2,'stroke-dasharray':'6,3'}));
  gm.forEach((v,i)=>{
    svg.appendChild(el('circle',{cx:sx(i).toFixed(1),cy:sy(v*maxY).toFixed(1),r:4,fill:'#38bdf8'}));
    const t=el('text',{x:sx(i),y:sy(v*maxY)-8,'text-anchor':'middle',fill:'#38bdf8','font-size':10});
    t.textContent='GM '+(v*100).toFixed(0)+'%'; svg.appendChild(t);
  });

  // Legend
  function leg(x,y,color,label,dashed){
    if(dashed) svg.appendChild(el('line',{x1:x,y1:y,x2:x+22,y2:y,stroke:color,'stroke-width':2,'stroke-dasharray':'6,3'}));
    else {
      svg.appendChild(el('rect',{x,y:y-6,width:22,height:12,fill:color,'fill-opacity':'0.8',rx:2}));
    }
    const t=el('text',{x:x+28,y:y+4,fill:'#e2e8f0','font-size':12});
    t.textContent=label; svg.appendChild(t);
  }
  leg(padL+10, padT+12, '#f87171', 'CAC ($)');
  leg(padL+120, padT+12, '#4ade80', 'LTV ($)');
  leg(padL+230, padT+12, '#38bdf8', 'Gross Margin %', true);
})();
</script>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Financial Model V3", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "financial_model_v3", "port": 8981}

    @app.get("/api/scenarios")
    async def scenarios():
        return {
            "break_even_arr_k": 380,
            "monthly_burn_k": 52,
            "runway_months": 18,
            "raise_m": 4,
            "headcount": {"y1": 3, "y2": 8, "y3": 18},
            "scenarios": {
                "base": {"break_even": "Q3 2027", "y3_arr_m": 3.2},
                "bull": {"break_even": "Q1 2027", "y3_arr_m": 6.8},
                "bear": {"break_even": "Q1 2028", "y3_arr_m": 1.4}
            }
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8981)
    else:
        print("FastAPI not available — starting fallback HTTP server on port 8981")
        HTTPServer(('0.0.0.0', 8981), Handler).serve_forever()
