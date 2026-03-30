#!/usr/bin/env python3
"""
model_comparison_portal.py — Head-to-head GR00T checkpoint comparison portal.

Design partners can compare any two GR00T checkpoints side by side.
Displays success rate, latency, cost, and failure analysis for both models,
then declares a winner based on Fisher exact test significance.

Usage:
    python src/api/model_comparison_portal.py --port 8012
    python src/api/model_comparison_portal.py --mock

Endpoints:
    GET  /                     HTML dashboard with comparison history + quick-compare form
    POST /compare              Form submit → runs comparison → redirects to /results/{id}
    GET  /results/{id}         Full comparison result page (side-by-side cards)
    GET  /api/compare          JSON comparison (same params as POST /compare)
    GET  /api/history          List of past comparisons (JSON)
    GET  /health               Health check
"""

import argparse
import math
import random
import sqlite3
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    print("pip install fastapi uvicorn pydantic")
    raise

# ── Constants ──────────────────────────────────────────────────────────────────

DB_PATH = "/tmp/model_comparisons.db"
OCI_USD_PER_HR = 3.06
OCI_THROUGHPUT_ITS = 2.35  # steps/sec, A100

# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comparisons (
            id          TEXT PRIMARY KEY,
            model_a     TEXT NOT NULL,
            model_b     TEXT NOT NULL,
            n_episodes  INTEGER NOT NULL,
            winner      TEXT,
            a_success   REAL,
            b_success   REAL,
            a_latency_ms REAL,
            b_latency_ms REAL,
            delta_success REAL,
            p_value     REAL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

_db: sqlite3.Connection = None  # initialised in startup

# ── Mock eval logic ────────────────────────────────────────────────────────────

_SUCCESS_HINTS = {
    "bc_baseline":    0.05,
    "bc_500demo":     0.05,
    "bc_1000demo":    0.10,
    "dagger_run1":    0.15,
    "dagger_run2":    0.25,
    "dagger_run3":    0.40,
    "dagger_run4":    0.65,
    "dagger_run5":    0.70,
    "dagger_run6":    0.75,
    "gr00t_n1":       0.50,
    "gr00t_n1_6":     0.60,
}

def _hint_for_model(name: str) -> float:
    """Extract success rate hint from model name (case-insensitive substring match)."""
    lower = name.lower().replace("-", "_").replace(" ", "_")
    for key, val in _SUCCESS_HINTS.items():
        if key in lower:
            return val
    return 0.20  # default

def _mock_eval(model_name: str, n_episodes: int, seed: int) -> tuple[float, float]:
    """Return (success_rate, latency_ms) for a model."""
    rng = random.Random(seed ^ hash(model_name) & 0xFFFF_FFFF)
    base = _hint_for_model(model_name)
    # add gaussian noise clamped to [0, 1]
    noise = rng.gauss(0, 0.06)
    rate = min(1.0, max(0.0, base + noise))
    # simulate per-episode outcomes for a more realistic success count
    successes = sum(1 for _ in range(n_episodes) if rng.random() < rate)
    actual_rate = successes / n_episodes if n_episodes else 0.0
    # latency: base ~220ms ± 30ms per model (faster models are often bigger/worse)
    latency = max(80.0, rng.gauss(220, 30))
    return actual_rate, round(latency, 1)

# ── Statistics (Fisher exact approximation) ────────────────────────────────────

def _fisher_p_value(a_success: float, b_success: float, n: int) -> float:
    """
    Approximate p-value from Fisher exact test on two proportions.
    Uses normal approximation for speed; returns 1.0 if indeterminate.
    """
    a_k = round(a_success * n)
    b_k = round(b_success * n)
    # pooled proportion
    p_pool = (a_k + b_k) / (2 * n) if n > 0 else 0.5
    if p_pool in (0.0, 1.0):
        return 1.0
    se = math.sqrt(p_pool * (1 - p_pool) * (2 / n))
    if se == 0:
        return 1.0
    z = abs(a_success - b_success) / se
    # two-tailed p from normal CDF approximation (Abramowitz & Stegun)
    t = 1.0 / (1.0 + 0.2316419 * z)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    p = 2.0 * (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z) * poly
    return min(1.0, max(0.0, p))

# ── ComparisonResult ───────────────────────────────────────────────────────────

@dataclass
class ComparisonResult:
    id: str
    model_a: str
    model_b: str
    n_episodes: int
    a_success_rate: float
    b_success_rate: float
    a_latency_ms: float
    b_latency_ms: float
    delta_success: float       # b - a (positive means B wins on success)
    p_value: float
    winner: str                # "model_a" | "model_b" | "tie"
    confidence: str            # "high" | "medium" | "low"
    created_at: str

def _confidence(p: float) -> str:
    if p < 0.05:
        return "high"
    if p < 0.15:
        return "medium"
    return "low"

def run_comparison(
    model_a: str,
    model_b: str,
    n_episodes: int = 20,
    seed: int = 42,
) -> ComparisonResult:
    a_rate, a_lat = _mock_eval(model_a, n_episodes, seed)
    b_rate, b_lat = _mock_eval(model_b, n_episodes, seed + 1)
    delta = round(b_rate - a_rate, 4)
    p = round(_fisher_p_value(a_rate, b_rate, n_episodes), 4)
    conf = _confidence(p)

    if p < 0.10:
        winner = "model_b" if b_rate > a_rate else "model_a"
    else:
        winner = "tie"

    return ComparisonResult(
        id=str(uuid.uuid4())[:8],
        model_a=model_a,
        model_b=model_b,
        n_episodes=n_episodes,
        a_success_rate=round(a_rate, 4),
        b_success_rate=round(b_rate, 4),
        a_latency_ms=a_lat,
        b_latency_ms=b_lat,
        delta_success=delta,
        p_value=p,
        winner=winner,
        confidence=conf,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

def _save(result: ComparisonResult) -> None:
    _db.execute(
        """INSERT OR REPLACE INTO comparisons
           (id, model_a, model_b, n_episodes, winner, a_success, b_success,
            a_latency_ms, b_latency_ms, delta_success, p_value, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (result.id, result.model_a, result.model_b, result.n_episodes,
         result.winner, result.a_success_rate, result.b_success_rate,
         result.a_latency_ms, result.b_latency_ms, result.delta_success,
         result.p_value, result.created_at),
    )
    _db.commit()

def _load(comparison_id: str) -> Optional[sqlite3.Row]:
    return _db.execute("SELECT * FROM comparisons WHERE id=?", (comparison_id,)).fetchone()

def _history(limit: int = 10) -> list[sqlite3.Row]:
    return _db.execute(
        "SELECT * FROM comparisons ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()

def _seed_records() -> None:
    """Pre-seed 3 comparison records on startup if DB is empty."""
    if _db.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0] > 0:
        return
    seeds = [
        ("bc_baseline", "dagger_run4", 20, 7),
        ("dagger_run4", "dagger_run5", 20, 13),
        ("bc_500demo", "bc_1000demo", 20, 21),
    ]
    for a, b, n, s in seeds:
        r = run_comparison(a, b, n, s)
        _save(r)

# ── Cost helper ────────────────────────────────────────────────────────────────

def _cost_per_episode(latency_ms: float) -> float:
    """USD cost per eval episode (single inference call)."""
    return (latency_ms / 1000.0 / 3600.0) * OCI_USD_PER_HR

# ── HTML helpers ──────────────────────────────────────────────────────────────

_STYLE = """
<style>
  :root{--bg:#0f172a;--card:#1e293b;--border:#334155;--red:#C74634;--green:#22c55e;--yellow:#eab308;--text:#f1f5f9;--muted:#94a3b8}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:var(--red);font-size:1.6rem;margin-bottom:4px}
  h2{font-size:1.1rem;margin-bottom:12px;color:var(--muted)}
  h3{font-size:1rem;margin-bottom:8px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;margin-bottom:20px}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{text-align:left;color:var(--muted);padding:6px 8px;border-bottom:1px solid var(--border)}
  td{padding:6px 8px;border-bottom:1px solid #1e293b}
  .badge{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:.75rem;font-weight:600}
  .high{background:#14532d;color:#86efac}.medium{background:#713f12;color:#fde68a}.low{background:#1e293b;color:var(--muted)}
  .win{color:var(--green)}.tie{color:var(--yellow)}.lose{color:var(--red)}
  form label{display:block;color:var(--muted);font-size:.8rem;margin-bottom:4px;margin-top:12px}
  form input,form select{width:100%;background:#0f172a;border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px 10px;font-size:.9rem}
  .btn{background:var(--red);color:#fff;border:none;border-radius:6px;padding:10px 20px;font-size:.95rem;cursor:pointer;margin-top:16px;width:100%}
  .btn:hover{opacity:.85}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  .bar-wrap{background:#0f172a;border-radius:6px;height:18px;overflow:hidden;margin:6px 0}
  .bar{height:18px;border-radius:6px;transition:width .4s}
  .bar-a{background:#3b82f6}.bar-b{background:var(--red)}
  .stat-label{color:var(--muted);font-size:.8rem}
  .stat-val{font-size:1.4rem;font-weight:700}
  .winner-box{border:2px solid var(--green);border-radius:10px;padding:16px;margin-bottom:20px;background:#052e16}
  .tie-box{border:2px solid var(--yellow);border-radius:10px;padding:16px;margin-bottom:20px;background:#1c1003}
  a{color:#60a5fa;text-decoration:none}.a:hover{text-decoration:underline}
  .back{display:inline-block;margin-bottom:16px;color:var(--muted);font-size:.85rem}
</style>
"""

def _pct(v: float) -> str:
    return f"{v*100:.1f}%"

def _row_winner_class(winner: str, model: str) -> str:
    if winner == "tie":
        return "tie"
    return "win" if winner == model else "lose"

def _html_dashboard(rows: list) -> str:
    history_rows = ""
    for r in rows:
        wc = "win" if r["winner"] != "tie" else "tie"
        winner_label = r["winner"].replace("model_", "Model ").upper() if r["winner"] != "tie" else "TIE"
        conf_badge = f'<span class="badge {r["winner"] if r["winner"]!="tie" else "low"}">{r["winner"][:3].upper() if r["winner"]!="tie" else "TIE"}</span>'
        conf_badge = f'<span class="badge {["high","medium","low"][["high","medium","low"].index(r["winner"]) if r["winner"] in ["high","medium","low"] else 2]}"></span>'
        # simpler: just show winner text
        history_rows += f"""<tr>
          <td><a href="/results/{r['id']}">{r['id']}</a></td>
          <td>{r['model_a']}</td>
          <td>{r['model_b']}</td>
          <td>{r['n_episodes']}</td>
          <td class="win">{_pct(r['a_success'])}</td>
          <td class="win">{_pct(r['b_success'])}</td>
          <td class="{'win' if r['winner']=='model_b' else 'lose' if r['winner']=='model_a' else 'tie'}">{winner_label}</td>
          <td>{r['p_value']:.3f}</td>
          <td>{r['created_at'][:10]}</td>
        </tr>"""
    return f"""<!DOCTYPE html><html><head><title>Model Comparison Portal</title>{_STYLE}</head><body>
<h1>Model Comparison Portal</h1>
<h2>OCI Robot Cloud — GR00T Checkpoint Evaluator</h2>
<div class="grid2">
  <div>
    <div class="card">
      <h3>Recent Comparisons</h3>
      <table>
        <thead><tr><th>ID</th><th>Model A</th><th>Model B</th><th>N</th><th>A%</th><th>B%</th><th>Winner</th><th>p</th><th>Date</th></tr></thead>
        <tbody>{history_rows}</tbody>
      </table>
    </div>
  </div>
  <div>
    <div class="card">
      <h3>Run New Comparison</h3>
      <form method="POST" action="/compare">
        <label>Model A (checkpoint name)</label>
        <input name="model_a" placeholder="e.g. bc_baseline" required>
        <label>Model B (checkpoint name)</label>
        <input name="model_b" placeholder="e.g. dagger_run4" required>
        <label>Number of Episodes</label>
        <select name="n_episodes">
          <option value="10">10</option>
          <option value="20" selected>20</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
        <button class="btn" type="submit">Run Comparison</button>
      </form>
    </div>
    <div class="card">
      <h3>Known Checkpoints</h3>
      <table>
        <thead><tr><th>Name</th><th>Approx. Success</th></tr></thead>
        <tbody>
          {''.join(f"<tr><td>{k}</td><td>{_pct(v)}</td></tr>" for k,v in _SUCCESS_HINTS.items())}
        </tbody>
      </table>
    </div>
  </div>
</div>
</body></html>"""

def _html_result(r: sqlite3.Row) -> str:
    winner_name = r["model_a"] if r["winner"] == "model_a" else (r["model_b"] if r["winner"] == "model_b" else None)
    a_pct = r["a_success"] * 100
    b_pct = r["b_success"] * 100
    a_cost = _cost_per_episode(r["a_latency_ms"]) * r["n_episodes"]
    b_cost = _cost_per_episode(r["b_latency_ms"]) * r["n_episodes"]
    max_pct = max(a_pct, b_pct, 1.0)

    if r["winner"] == "tie":
        verdict_box = f"""<div class="tie-box">
          <strong style="color:#eab308;font-size:1.1rem">TIE — No Statistically Significant Difference</strong>
          <p style="margin-top:8px;color:#94a3b8">p={r['p_value']:.3f} &gt; 0.10. Increase episode count for more power.</p>
        </div>"""
        rec = f"Neither model is decisively better. Run with ≥50 episodes for a clearer signal."
    else:
        loser = r["model_b"] if r["winner"] == "model_a" else r["model_a"]
        delta_pct = abs(r["delta_success"]) * 100
        verdict_box = f"""<div class="winner-box">
          <strong style="color:#22c55e;font-size:1.1rem">Winner: {winner_name}</strong>
          <p style="margin-top:8px;color:#94a3b8">
            +{delta_pct:.1f}% success rate over {loser} &nbsp;|&nbsp;
            p={r['p_value']:.3f} &nbsp;|&nbsp; Confidence: <span class="badge {r.get('confidence','low') if isinstance(r,dict) else 'low'}">{r['p_value']:.3f}</span>
          </p>
        </div>"""
        conf = _confidence(r["p_value"])
        rec = (
            f"Deploy {winner_name}. Confidence is {'high' if conf=='high' else 'moderate' if conf=='medium' else 'low'} "
            f"(p={r['p_value']:.3f}). {'Ready for production rollout.' if conf=='high' else 'Consider collecting more episodes before full rollout.'}"
        )

    return f"""<!DOCTYPE html><html><head><title>Comparison {r['id']}</title>{_STYLE}</head><body>
<a class="back" href="/">← Back to Dashboard</a>
<h1>Comparison Result: {r['id']}</h1>
<h2>{r['model_a']} vs {r['model_b']} — {r['n_episodes']} episodes</h2>
{verdict_box}
<div class="grid2">
  <div class="card">
    <h3 style="color:#3b82f6">Model A: {r['model_a']}</h3>
    <div class="stat-label">Success Rate</div>
    <div class="stat-val {'win' if r['winner']=='model_a' else ''}">{_pct(r['a_success'])}</div>
    <div class="bar-wrap"><div class="bar bar-a" style="width:{a_pct/max_pct*100:.1f}%"></div></div>
    <div class="stat-label" style="margin-top:10px">Avg Latency</div>
    <div class="stat-val">{r['a_latency_ms']:.0f} ms</div>
    <div class="stat-label" style="margin-top:10px">Est. Eval Cost</div>
    <div class="stat-val">${a_cost:.4f}</div>
  </div>
  <div class="card">
    <h3 style="color:var(--red)">Model B: {r['model_b']}</h3>
    <div class="stat-label">Success Rate</div>
    <div class="stat-val {'win' if r['winner']=='model_b' else ''}">{_pct(r['b_success'])}</div>
    <div class="bar-wrap"><div class="bar bar-b" style="width:{b_pct/max_pct*100:.1f}%"></div></div>
    <div class="stat-label" style="margin-top:10px">Avg Latency</div>
    <div class="stat-val">{r['b_latency_ms']:.0f} ms</div>
    <div class="stat-label" style="margin-top:10px">Est. Eval Cost</div>
    <div class="stat-val">${b_cost:.4f}</div>
  </div>
</div>
<div class="card">
  <h3>Failure Analysis</h3>
  <table>
    <thead><tr><th>Metric</th><th>Model A</th><th>Model B</th><th>Delta</th></tr></thead>
    <tbody>
      <tr><td>Success rate</td><td>{_pct(r['a_success'])}</td><td>{_pct(r['b_success'])}</td>
          <td class="{'win' if r['delta_success']>0 else 'lose'}">{r['delta_success']*100:+.1f}%</td></tr>
      <tr><td>Failure rate</td><td>{_pct(1-r['a_success'])}</td><td>{_pct(1-r['b_success'])}</td>
          <td class="{'lose' if r['delta_success']>0 else 'win'}">{-r['delta_success']*100:+.1f}%</td></tr>
      <tr><td>Latency</td><td>{r['a_latency_ms']:.0f} ms</td><td>{r['b_latency_ms']:.0f} ms</td>
          <td>{r['b_latency_ms']-r['a_latency_ms']:+.0f} ms</td></tr>
      <tr><td>Cost / episode</td><td>${_cost_per_episode(r['a_latency_ms']):.5f}</td>
          <td>${_cost_per_episode(r['b_latency_ms']):.5f}</td><td>—</td></tr>
      <tr><td>p-value (Fisher)</td><td colspan="2">{r['p_value']:.4f}</td>
          <td class="badge {'high' if r['p_value']<0.05 else 'medium' if r['p_value']<0.15 else 'low'}">{_confidence(r['p_value'])}</td></tr>
    </tbody>
  </table>
</div>
<div class="card">
  <h3>Recommendation</h3>
  <p style="color:var(--muted)">{rec}</p>
</div>
</body></html>"""

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="Model Comparison Portal", version="1.0.0")

class CompareRequest(BaseModel):
    model_a: str
    model_b: str
    n_episodes: int = 20
    seed: int = 42

@app.on_event("startup")
def _startup():
    global _db
    _db = _init_db()
    _seed_records()

@app.get("/", response_class=HTMLResponse)
def dashboard():
    rows = _history(10)
    return _html_dashboard(rows)

@app.post("/compare")
def compare_form(
    model_a: str = Form(...),
    model_b: str = Form(...),
    n_episodes: int = Form(20),
):
    result = run_comparison(model_a, model_b, n_episodes)
    _save(result)
    return RedirectResponse(url=f"/results/{result.id}", status_code=303)

@app.get("/results/{comparison_id}", response_class=HTMLResponse)
def result_page(comparison_id: str):
    row = _load(comparison_id)
    if row is None:
        return HTMLResponse(f"<h1>Not found: {comparison_id}</h1>", status_code=404)
    return _html_result(row)

@app.get("/api/compare")
def api_compare(model_a: str, model_b: str, n_episodes: int = 20, seed: int = 42):
    result = run_comparison(model_a, model_b, n_episodes, seed)
    _save(result)
    return JSONResponse(asdict(result))

@app.get("/api/history")
def api_history(limit: int = 10):
    rows = _history(limit)
    return JSONResponse([dict(r) for r in rows])

@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "service": "model_comparison_portal", "port": 8012})

# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model Comparison Portal")
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--mock", action="store_true", help="Force mock eval (always true for now)")
    args = parser.parse_args()

    print(f"Starting Model Comparison Portal on http://{args.host}:{args.port}")
    print(f"  Dashboard:  http://localhost:{args.port}/")
    print(f"  API:        http://localhost:{args.port}/api/compare?model_a=bc_baseline&model_b=dagger_run4")
    print(f"  Health:     http://localhost:{args.port}/health")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
