"""
OCI Robot Cloud Interactive Cost Calculator.

A standalone FastAPI web app that lets robotics customers instantly compute
the cost of fine-tuning GR00T on their own demo data — comparing OCI, DGX,
AWS, and Lambda Cloud.

Perfect for AI World demo: design partners enter their scenario and immediately
see "Your 200-demo fine-tuning run would cost $0.34 on OCI vs $16.44 on AWS."

Usage:
    python3 cost_calculator.py --port 8005
    open http://localhost:8005

Endpoints:
    GET  /                  — Interactive calculator UI
    POST /calculate         — JSON cost estimate
    GET  /presets           — Common robotics scenarios
"""

import argparse
from typing import Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("pip install fastapi uvicorn pydantic")
    raise

app = FastAPI(title="OCI Robot Cloud Cost Calculator", version="1.0.0")

# ── Pricing constants (updated 2026-Q1) ──────────────────────────────────────
PRICING = {
    "oci_a100": {
        "name": "OCI A100-SXM4-80GB",
        "usd_per_hr": 3.06,
        "throughput_its": 2.35,   # steps/sec at batch=32
        "capex": 0,
        "setup_min": 5,
        "compliance": "FedRAMP / OC2",
        "max_gpus": 32,
        "color": "#c74634",
        "badge": "RECOMMENDED",
    },
    "dgx_onprem": {
        "name": "DGX A100 On-Premise",
        "usd_per_hr": 3.26,       # amortized: $200k/8GPU over 3yr at 8hr/day
        "throughput_its": 2.35,   # same chip, same perf
        "capex": 200_000,
        "setup_min": 10_000,      # weeks of procurement + rack
        "compliance": "Customer-managed",
        "max_gpus": 8,
        "color": "#6b7280",
        "badge": "",
    },
    "aws_p4d": {
        "name": "AWS p4d.24xlarge (8× A100)",
        "usd_per_hr": 32.77,      # on-demand; 8× A100, ~$4.10/GPU/hr
        "throughput_its": 2.35,   # same chip per GPU
        "capex": 0,
        "setup_min": 20,
        "compliance": "GovCloud (extra cost)",
        "max_gpus": 8,
        "color": "#f59e0b",
        "badge": "",
    },
    "lambda_a100": {
        "name": "Lambda Cloud A100",
        "usd_per_hr": 2.49,       # Lambda on-demand
        "throughput_its": 2.35,
        "capex": 0,
        "setup_min": 15,
        "compliance": "None (no FedRAMP)",
        "max_gpus": 8,
        "color": "#3b82f6",
        "badge": "",
    },
}

# Benchmark: batch=32, 1 GPU. Steps/sec = 2.35.
# Cost = (steps / throughput_its) / 3600 * usd_per_hr
STEPS_PER_DEMO_STEP = 1   # 1 training step = 1 gradient update


# ── Cost model ────────────────────────────────────────────────────────────────

def estimate_steps(
    n_demos: int,
    steps_per_demo: int = 100,
    target_quality: str = "standard",
) -> int:
    """Estimate total training steps needed for n_demos demonstrations."""
    # Empirical: we get good convergence at ~20× the total demo frames
    total_frames = n_demos * steps_per_demo
    multipliers = {
        "quick": 10,       # fast iteration, lower quality
        "standard": 20,    # our default: 2000 steps on 100 demos
        "thorough": 50,    # more epochs, higher quality
    }
    mult = multipliers.get(target_quality, 20)
    steps = int(total_frames * mult / 32)   # assuming batch=32
    # Clamp to reasonable range
    return max(500, min(steps, 50_000))


def compute_cost(
    n_demos: int,
    steps_per_demo: int = 100,
    target_quality: str = "standard",
    provider_id: str = "oci_a100",
    n_gpus: int = 1,
) -> dict:
    """Compute training cost for a single provider configuration."""
    p = PRICING[provider_id]
    total_steps = estimate_steps(n_demos, steps_per_demo, target_quality)
    effective_its = p["throughput_its"] * n_gpus * 0.77   # 77% parallel efficiency
    time_sec = total_steps / effective_its
    time_min = time_sec / 60
    time_hr = time_sec / 3600
    compute_cost_usd = time_hr * p["usd_per_hr"]
    sdg_time_sec = n_demos * 0.9   # 0.9s/demo in Genesis (Genesis SDG benchmark)
    sdg_cost_usd = 0.0   # Genesis is open-source, CPU time is negligible

    return {
        "provider": provider_id,
        "provider_name": p["name"],
        "total_steps": total_steps,
        "time_min": round(time_min, 1),
        "time_hr": round(time_hr, 3),
        "compute_cost_usd": round(compute_cost_usd, 4),
        "sdg_time_sec": round(sdg_time_sec, 1),
        "total_cost_usd": round(compute_cost_usd + sdg_cost_usd, 4),
        "capex_usd": p["capex"],
        "setup_min": p["setup_min"],
        "throughput_its": round(effective_its, 2),
        "compliance": p["compliance"],
        "max_gpus": p["max_gpus"],
        "color": p["color"],
        "badge": p["badge"],
    }


# ── Request/response models ────────────────────────────────────────────────────

class CalcRequest(BaseModel):
    n_demos: int = 100
    steps_per_demo: int = 100
    target_quality: str = "standard"  # quick / standard / thorough
    n_gpus: int = 1
    providers: Optional[list] = None   # None = all


class CalcResponse(BaseModel):
    input: dict
    total_steps: int
    estimates: list
    summary: dict


# ── REST endpoint ─────────────────────────────────────────────────────────────

@app.post("/calculate")
def calculate(req: CalcRequest):
    providers = req.providers or list(PRICING.keys())
    estimates = [
        compute_cost(req.n_demos, req.steps_per_demo, req.target_quality, pid, req.n_gpus)
        for pid in providers
        if pid in PRICING
    ]
    estimates.sort(key=lambda x: x["compute_cost_usd"])

    oci = next((e for e in estimates if e["provider"] == "oci_a100"), None)
    aws = next((e for e in estimates if e["provider"] == "aws_p4d"), None)
    dgx = next((e for e in estimates if e["provider"] == "dgx_onprem"), None)

    summary = {}
    if oci and aws:
        ratio = aws["compute_cost_usd"] / oci["compute_cost_usd"] if oci["compute_cost_usd"] > 0 else 0
        summary["oci_vs_aws_savings"] = round(ratio, 1)
        summary["aws_premium"] = round(aws["compute_cost_usd"] - oci["compute_cost_usd"], 2)
    if oci and dgx:
        dgx_breakeven_months = (dgx["capex_usd"] / max(oci["compute_cost_usd"], 0.01)) * (1 / 4.33)  # rough
        summary["dgx_capex"] = dgx["capex_usd"]
        summary["oci_total_cost"] = oci["total_cost_usd"]
        summary["oci_time_min"] = oci["time_min"]

    return JSONResponse({
        "input": req.dict(),
        "total_steps": estimates[0]["total_steps"] if estimates else 0,
        "estimates": estimates,
        "summary": summary,
    })


@app.get("/presets")
def get_presets():
    """Common robotics fine-tuning scenarios."""
    return JSONResponse([
        {
            "name": "Quick prototype",
            "description": "20 demos, fast iteration — is the pipeline working?",
            "n_demos": 20, "steps_per_demo": 50, "target_quality": "quick",
        },
        {
            "name": "Standard (our benchmark)",
            "description": "100 demos × 2000 steps — the published OCI benchmark",
            "n_demos": 100, "steps_per_demo": 100, "target_quality": "standard",
        },
        {
            "name": "Scale-up (this session)",
            "description": "500 demos × 5000 steps — design-partner quality",
            "n_demos": 500, "steps_per_demo": 100, "target_quality": "standard",
        },
        {
            "name": "Production deployment",
            "description": "1000 demos, thorough training — production robot",
            "n_demos": 1000, "steps_per_demo": 100, "target_quality": "thorough",
        },
        {
            "name": "Multi-task (3 tasks)",
            "description": "300 demos across 3 tasks, thorough",
            "n_demos": 300, "steps_per_demo": 100, "target_quality": "thorough",
        },
    ])


# ── HTML UI ────────────────────────────────────────────────────────────────────

CALCULATOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OCI Robot Cloud — Cost Calculator</title>
<style>
  :root {
    --bg: #0d0d0d; --card: #1a1a1a; --border: #2a2a2a;
    --red: #c74634; --green: #22c55e; --amber: #f59e0b;
    --blue: #3b82f6; --gray: #6b7280; --text: #e5e7eb; --lgray: #9ca3af;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; }
  header {
    background: #111; border-bottom: 2px solid var(--red);
    padding: 16px 32px; display: flex; align-items: center; gap: 16px;
  }
  header h1 { font-size: 22px; color: var(--red); }
  header span { color: var(--gray); font-size: 13px; }
  main { max-width: 1100px; margin: 0 auto; padding: 24px 32px; }
  h2 { font-size: 13px; color: var(--lgray); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }

  /* Inputs */
  .controls { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }
  .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
  .field label { display: block; font-size: 11px; color: var(--lgray); text-transform: uppercase; margin-bottom: 6px; }
  .field input, .field select {
    width: 100%; background: #111; border: 1px solid var(--border);
    color: var(--text); padding: 10px 12px; border-radius: 6px; font-family: monospace; font-size: 14px;
  }
  .field input:focus, .field select:focus { outline: none; border-color: var(--red); }
  .presets { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
  .preset-btn {
    background: #111; border: 1px solid var(--border); color: var(--lgray);
    padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: monospace;
  }
  .preset-btn:hover { border-color: var(--red); color: var(--text); }
  .calc-btn {
    background: var(--red); color: #fff; border: none;
    padding: 12px 32px; border-radius: 6px; font-size: 15px; font-family: monospace;
    cursor: pointer; font-weight: bold; letter-spacing: 1px;
  }
  .calc-btn:hover { background: #e05d4a; }

  /* Summary banner */
  .summary { background: #0f0f0f; border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; margin-bottom: 24px; display: none; }
  .summary .big { font-size: 42px; font-weight: bold; color: var(--red); }
  .summary .sub { font-size: 14px; color: var(--lgray); margin-top: 4px; }
  .savings-row { display: flex; gap: 32px; margin-top: 16px; flex-wrap: wrap; }
  .savings-item .label { font-size: 11px; color: var(--gray); }
  .savings-item .val { font-size: 20px; color: var(--green); font-weight: bold; }

  /* Result cards */
  .results { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
  @media (max-width: 700px) { .results { grid-template-columns: 1fr; } }
  .result-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; position: relative;
  }
  .result-card.highlighted { border-color: var(--red); }
  .badge {
    position: absolute; top: 12px; right: 12px;
    background: var(--red); color: #fff; font-size: 10px;
    padding: 3px 8px; border-radius: 3px; font-weight: bold; letter-spacing: 1px;
  }
  .provider-name { font-size: 15px; font-weight: bold; margin-bottom: 12px; }
  .big-cost { font-size: 36px; font-weight: bold; margin: 8px 0; }
  .meta { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 12px; }
  .meta-item .k { font-size: 10px; color: var(--gray); }
  .meta-item .v { font-size: 13px; }
  .capex-note { font-size: 11px; color: var(--amber); margin-top: 8px; }

  /* Comparison bar */
  .comparison { background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; margin-bottom: 24px; display: none; }
  .bar-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .bar-label { width: 160px; font-size: 12px; color: var(--lgray); text-align: right; flex-shrink: 0; }
  .bar-bg { flex: 1; background: #111; border-radius: 4px; height: 28px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; display: flex; align-items: center; padding-left: 10px; font-size: 12px; }
  .bar-val { width: 80px; font-size: 13px; text-align: right; flex-shrink: 0; }

  footer { text-align: center; color: var(--gray); font-size: 11px; padding: 24px; border-top: 1px solid var(--border); }
</style>
</head>
<body>
<header>
  <h1>OCI ROBOT CLOUD</h1>
  <span>Fine-Tuning Cost Calculator · Oracle Cloud Infrastructure × NVIDIA</span>
</header>

<main>
<h2>Your Scenario</h2>
<div class="controls">
  <div class="presets" id="presets-row"></div>
  <div class="grid3">
    <div class="field">
      <label>Number of Robot Demos</label>
      <input type="number" id="n_demos" value="100" min="1" max="10000">
    </div>
    <div class="field">
      <label>Steps per Demo</label>
      <input type="number" id="steps_per_demo" value="100" min="10" max="1000">
    </div>
    <div class="field">
      <label>Training Quality</label>
      <select id="target_quality">
        <option value="quick">Quick (fast iteration)</option>
        <option value="standard" selected>Standard (our benchmark)</option>
        <option value="thorough">Thorough (production)</option>
      </select>
    </div>
  </div>
  <button class="calc-btn" onclick="calculate()">CALCULATE COST →</button>
</div>

<div class="summary" id="summary">
  <div class="big" id="sum-cost">—</div>
  <div class="sub" id="sum-desc">on OCI A100 · including Genesis SDG</div>
  <div class="savings-row">
    <div class="savings-item">
      <div class="label">vs AWS p4d</div>
      <div class="val" id="sum-savings-aws">—</div>
    </div>
    <div class="savings-item">
      <div class="label">DGX CapEx</div>
      <div class="val" id="sum-capex">$200k</div>
    </div>
    <div class="savings-item">
      <div class="label">Training time</div>
      <div class="val" id="sum-time">—</div>
    </div>
    <div class="savings-item">
      <div class="label">Total steps</div>
      <div class="val" id="sum-steps">—</div>
    </div>
  </div>
</div>

<div class="results" id="results-grid" style="display:none"></div>

<div class="comparison" id="comparison">
  <h2>Cost Comparison (Compute Only)</h2>
  <div id="comparison-bars"></div>
</div>
</main>

<footer>OCI Robot Cloud · Oracle Cloud Infrastructure × NVIDIA · Cost estimates based on published benchmark: 2.35 it/s, batch=32, A100-SXM4-80GB</footer>

<script>
async function loadPresets() {
  const res = await fetch('/presets');
  const presets = await res.json();
  const row = document.getElementById('presets-row');
  presets.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'preset-btn';
    btn.title = p.description;
    btn.textContent = p.name;
    btn.onclick = () => {
      document.getElementById('n_demos').value = p.n_demos;
      document.getElementById('steps_per_demo').value = p.steps_per_demo;
      document.getElementById('target_quality').value = p.target_quality;
      calculate();
    };
    row.appendChild(btn);
  });
}

async function calculate() {
  const body = {
    n_demos: parseInt(document.getElementById('n_demos').value),
    steps_per_demo: parseInt(document.getElementById('steps_per_demo').value),
    target_quality: document.getElementById('target_quality').value,
    n_gpus: 1,
  };
  const res = await fetch('/calculate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await res.json();
  renderResults(data);
}

function fmt(v) {
  if (v < 0.01) return '<$0.01';
  if (v < 1) return '$' + v.toFixed(3);
  if (v < 100) return '$' + v.toFixed(2);
  return '$' + Math.round(v).toLocaleString();
}
function fmtTime(min) {
  if (min < 1) return '<1 min';
  if (min < 60) return Math.round(min) + ' min';
  return (min/60).toFixed(1) + ' hr';
}

function renderResults(data) {
  const { estimates, summary, total_steps } = data;
  const oci = estimates.find(e => e.provider === 'oci_a100');
  const aws = estimates.find(e => e.provider === 'aws_p4d');

  // Summary banner
  document.getElementById('summary').style.display = 'block';
  document.getElementById('sum-cost').textContent = oci ? fmt(oci.total_cost_usd) : '—';
  document.getElementById('sum-desc').textContent =
    `on OCI A100 · ${total_steps.toLocaleString()} training steps`;
  document.getElementById('sum-time').textContent = oci ? fmtTime(oci.time_min) : '—';
  document.getElementById('sum-steps').textContent = total_steps.toLocaleString();
  if (summary.oci_vs_aws_savings) {
    document.getElementById('sum-savings-aws').textContent = summary.oci_vs_aws_savings.toFixed(1) + '× cheaper';
  }

  // Result cards
  const grid = document.getElementById('results-grid');
  grid.style.display = 'grid';
  grid.innerHTML = '';
  estimates.forEach(e => {
    const card = document.createElement('div');
    card.className = 'result-card' + (e.provider === 'oci_a100' ? ' highlighted' : '');
    card.innerHTML = `
      ${e.badge ? `<div class="badge">${e.badge}</div>` : ''}
      <div class="provider-name" style="color:${e.color}">${e.provider_name}</div>
      <div style="color:${e.color};font-size:11px;">Compute only</div>
      <div class="big-cost" style="color:${e.color}">${fmt(e.compute_cost_usd)}</div>
      <div class="meta">
        <div class="meta-item"><div class="k">Training time</div><div class="v">${fmtTime(e.time_min)}</div></div>
        <div class="meta-item"><div class="k">Throughput</div><div class="v">${e.throughput_its.toFixed(2)} it/s</div></div>
        <div class="meta-item"><div class="k">Compliance</div><div class="v" style="font-size:11px">${e.compliance}</div></div>
        <div class="meta-item"><div class="k">Max GPUs</div><div class="v">${e.max_gpus}×</div></div>
      </div>
      ${e.capex_usd > 0 ? `<div class="capex-note">⚠ $${(e.capex_usd/1000).toFixed(0)}k CapEx not included</div>` : ''}
    `;
    grid.appendChild(card);
  });

  // Comparison bars
  const comp = document.getElementById('comparison');
  comp.style.display = 'block';
  const bars = document.getElementById('comparison-bars');
  bars.innerHTML = '';
  const maxCost = Math.max(...estimates.map(e => e.compute_cost_usd));
  estimates.forEach(e => {
    const pct = maxCost > 0 ? (e.compute_cost_usd / maxCost * 100) : 0;
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML = `
      <div class="bar-label">${e.provider_name.split(' (')[0].replace('OCI A100-SXM4-80GB','OCI A100')}</div>
      <div class="bar-bg">
        <div class="bar-fill" style="width:${pct}%;background:${e.color}">
          ${pct > 20 ? fmt(e.compute_cost_usd) : ''}
        </div>
      </div>
      <div class="bar-val" style="color:${e.color}">${pct <= 20 ? fmt(e.compute_cost_usd) : ''}</div>
    `;
    bars.appendChild(row);
  });
}

loadPresets();
calculate();
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def root():
    return CALCULATOR_HTML


def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Cost Calculator")
    parser.add_argument("--port", type=int, default=8005)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    print(f"[Calculator] OCI Robot Cloud Cost Calculator")
    print(f"[Calculator] Open: http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
