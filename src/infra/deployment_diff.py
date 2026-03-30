"""Deployment Config Diff Viewer — OCI Robot Cloud — port 8158"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

SNAPSHOTS = {
    "snap_001": {
        "id": "snap_001",
        "date": "2026-02-15",
        "config": {
            "model": "dagger_run9_v2",
            "chunk_size": 16,
            "lora_rank": 16,
            "batch_size": 1,
            "fp16": True,
            "temperature": 0.1,
            "max_seq_len": 1024,
            "region": "ashburn",
            "replicas": 1,
        },
    },
    "snap_002": {
        "id": "snap_002",
        "date": "2026-03-01",
        "config": {
            "model": "groot_finetune_v2",
            "chunk_size": 16,
            "lora_rank": 16,
            "batch_size": 1,
            "fp16": True,
            "temperature": 0.1,
            "max_seq_len": 1024,
            "region": "ashburn",
            "replicas": 2,
        },
    },
    "snap_003": {
        "id": "snap_003",
        "date": "2026-03-15",
        "config": {
            "model": "groot_finetune_v2",
            "chunk_size": 16,
            "lora_rank": 16,
            "batch_size": 2,
            "fp16": True,
            "temperature": 0.08,
            "max_seq_len": 2048,
            "region": "ashburn",
            "replicas": 2,
        },
    },
    "snap_current": {
        "id": "snap_current",
        "date": "2026-03-30",
        "config": {
            "model": "groot_finetune_v2",
            "chunk_size": 16,
            "lora_rank": 16,
            "batch_size": 2,
            "fp16": True,
            "temperature": 0.08,
            "max_seq_len": 2048,
            "region": "ashburn",
            "replicas": 2,
        },
    },
}

TIMELINE_CHANGES = {
    ("snap_001", "snap_002"): 3,  # model, replicas, (batch/temp/seq same)
    ("snap_002", "snap_003"): 3,  # batch_size, temperature, max_seq_len
    ("snap_003", "snap_current"): 0,
}

CHANGE_IMPACT = [
    {"key": "batch_size", "from": 1, "to": 2, "impact": "batch_size 1→2 improved throughput ~40%"},
    {"key": "temperature", "from": 0.1, "to": 0.08, "impact": "temperature 0.1→0.08 improved action precision"},
    {"key": "model", "from": "dagger_run9_v2", "to": "groot_finetune_v2", "impact": "model upgrade added +7pp success rate"},
    {"key": "max_seq_len", "from": 1024, "to": 2048, "impact": "max_seq_len 1024→2048 enables longer task horizons"},
    {"key": "replicas", "from": 1, "to": 2, "impact": "replicas 1→2 doubled serving capacity"},
]

# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------

def compute_diff(id_from: str, id_to: str):
    if id_from not in SNAPSHOTS:
        raise KeyError(f"Unknown snapshot: {id_from}")
    if id_to not in SNAPSHOTS:
        raise KeyError(f"Unknown snapshot: {id_to}")
    cfg_from = SNAPSHOTS[id_from]["config"]
    cfg_to = SNAPSHOTS[id_to]["config"]
    all_keys = sorted(set(list(cfg_from.keys()) + list(cfg_to.keys())))
    rows = []
    for k in all_keys:
        v_from = cfg_from.get(k)
        v_to = cfg_to.get(k)
        if k not in cfg_from:
            status = "added"
        elif k not in cfg_to:
            status = "removed"
        elif v_from != v_to:
            status = "changed"
        else:
            status = "unchanged"
        rows.append({"key": k, "from": v_from, "to": v_to, "status": status})
    return rows

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def diff_svg(rows) -> str:
    W, H = 680, max(280, 40 + len(rows) * 30 + 20)
    col_key = 20
    col_mid = 200
    col_from = 220
    col_to = 450
    row_h = 30
    y_start = 50

    COLOR_MAP = {
        "changed":   ("#78350f", "#fbbf24"),   # bg, text (amber)
        "added":     ("#14532d", "#4ade80"),   # green
        "removed":   ("#450a0a", "#f87171"),   # red
        "unchanged": ("#1e293b", "#94a3b8"),   # gray
    }

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:monospace">')
    # header
    lines.append(f'<text x="{col_key}" y="30" fill="#94a3b8" font-size="12">KEY</text>')
    lines.append(f'<text x="{col_from}" y="30" fill="#94a3b8" font-size="12">FROM</text>')
    lines.append(f'<text x="{col_to}" y="30" fill="#94a3b8" font-size="12">TO</text>')
    lines.append(f'<line x1="{col_key}" y1="36" x2="{W-col_key}" y2="36" stroke="#334155" stroke-width="1"/>')

    for i, row in enumerate(rows):
        y = y_start + i * row_h
        bg, fg = COLOR_MAP[row["status"]]
        lines.append(f'<rect x="{col_key-4}" y="{y-14}" width="{W-2*(col_key-4)}" height="24" rx="3" fill="{bg}"/>')
        lines.append(f'<text x="{col_key}" y="{y+2}" fill="{fg}" font-size="12">{row["key"]}</text>')
        from_val = "" if row["from"] is None else str(row["from"])
        to_val = "" if row["to"] is None else str(row["to"])
        lines.append(f'<text x="{col_from}" y="{y+2}" fill="{fg}" font-size="12">{from_val}</text>')
        lines.append(f'<text x="{col_to}" y="{y+2}" fill="{fg}" font-size="12">{to_val}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def timeline_svg() -> str:
    W, H = 680, 120
    snap_order = ["snap_001", "snap_002", "snap_003", "snap_current"]
    labels = ["Feb 15", "Mar 01", "Mar 15", "Mar 30 (current)"]
    changes = [3, 3, 0]
    xs = [80, 240, 400, 580]
    y_dot = 60

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:sans-serif">')
    # connecting lines
    for i in range(len(xs) - 1):
        x1, x2 = xs[i], xs[i + 1]
        lines.append(f'<line x1="{x1}" y1="{y_dot}" x2="{x2}" y2="{y_dot}" stroke="#334155" stroke-width="2"/>')
        mid_x = (x1 + x2) // 2
        ch = changes[i]
        clr = "#fbbf24" if ch > 0 else "#4ade80"
        label = f"{ch} change{'s' if ch != 1 else ''}"
        lines.append(f'<text x="{mid_x}" y="{y_dot - 12}" fill="{clr}" font-size="10" text-anchor="middle">{label}</text>')

    # dots
    for i, (x, sid, lbl) in enumerate(zip(xs, snap_order, labels)):
        clr = "#C74634" if sid == "snap_current" else "#38bdf8"
        lines.append(f'<circle cx="{x}" cy="{y_dot}" r="8" fill="{clr}" style="cursor:pointer"/>')
        lines.append(f'<text x="{x}" y="{y_dot + 22}" fill="#94a3b8" font-size="10" text-anchor="middle">{lbl}</text>')
        lines.append(f'<text x="{x}" y="{y_dot + 34}" fill="#64748b" font-size="9" text-anchor="middle">{sid}</text>')

    lines.append('</svg>')
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html(from_id="snap_001", to_id="snap_current") -> str:
    try:
        rows = compute_diff(from_id, to_id)
    except KeyError as e:
        rows = []
    dsvg = diff_svg(rows)
    tsvg = timeline_svg()

    snap_options_from = "".join(
        f'<option value="{k}" {"selected" if k==from_id else ""}>{k} ({v["date"]})</option>'
        for k, v in SNAPSHOTS.items()
    )
    snap_options_to = "".join(
        f'<option value="{k}" {"selected" if k==to_id else ""}>{k} ({v["date"]})</option>'
        for k, v in SNAPSHOTS.items()
    )

    changed_count = sum(1 for r in rows if r["status"] == "changed")
    added_count   = sum(1 for r in rows if r["status"] == "added")
    removed_count = sum(1 for r in rows if r["status"] == "removed")

    impact_html = "".join(
        f'<li style="margin-bottom:6px"><span style="color:#38bdf8;font-weight:bold">{item["key"]}</span>: {item["impact"]}</li>'
        for item in CHANGE_IMPACT
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Deployment Diff Viewer — OCI Robot Cloud</title>
<style>
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:sans-serif; padding:24px; }}
  h1 {{ color:#C74634; font-size:22px; margin-bottom:4px; }}
  .subtitle {{ color:#64748b; font-size:13px; margin-bottom:20px; }}
  .card {{ background:#1e293b; border-radius:10px; padding:18px; margin-bottom:20px; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; margin-right:6px; }}
  .badge-amber {{ background:#78350f; color:#fbbf24; }}
  .badge-green {{ background:#14532d; color:#4ade80; }}
  .badge-red   {{ background:#450a0a; color:#f87171; }}
  select {{ background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:6px; padding:4px 8px; font-size:13px; }}
  button {{ background:#C74634; color:#fff; border:none; border-radius:6px; padding:6px 16px; cursor:pointer; font-size:13px; }}
  button:hover {{ background:#a83929; }}
  ul {{ margin:8px 0; padding-left:20px; color:#94a3b8; font-size:13px; }}
</style>
</head>
<body>
<h1>Deployment Config Diff Viewer</h1>
<p class="subtitle">OCI Robot Cloud · port 8158 · Compare deployment snapshots side-by-side</p>

<div class="card">
  <div style="margin-bottom:14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <label style="font-size:13px;color:#94a3b8">From:</label>
    <select id="fromSel">{snap_options_from}</select>
    <label style="font-size:13px;color:#94a3b8">To:</label>
    <select id="toSel">{snap_options_to}</select>
    <button onclick="reloadDiff()">Compare</button>
    <span class="badge badge-amber">{changed_count} changed</span>
    <span class="badge badge-green">{added_count} added</span>
    <span class="badge badge-red">{removed_count} removed</span>
  </div>
  {dsvg}
</div>

<div class="card">
  <h2 style="font-size:15px;color:#38bdf8;margin-top:0">Snapshot Timeline</h2>
  {tsvg}
</div>

<div class="card">
  <h2 style="font-size:15px;color:#38bdf8;margin-top:0">Change Impact Analysis (snap_001 → snap_current)</h2>
  <ul>{impact_html}</ul>
</div>

<script>
function reloadDiff(){{
  const f = document.getElementById('fromSel').value;
  const t = document.getElementById('toSel').value;
  window.location.href = '/?from=' + f + '&to=' + t;
}}
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Deployment Diff Viewer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(from_: str = "snap_001", to: str = "snap_current"):
        # FastAPI query param named 'from' conflicts with Python keyword — alias via alias
        return build_html(from_, to)

    @app.get("/snapshots")
    def list_snapshots():
        return [{"id": k, "date": v["date"]} for k, v in SNAPSHOTS.items()]

    @app.get("/snapshots/{snapshot_id}")
    def get_snapshot(snapshot_id: str):
        if snapshot_id not in SNAPSHOTS:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return SNAPSHOTS[snapshot_id]

    @app.get("/diff")
    def get_diff(from_: str = "snap_001", to: str = "snap_current"):
        try:
            rows = compute_diff(from_, to)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {
            "from": from_,
            "to": to,
            "rows": rows,
            "summary": {
                "changed": sum(1 for r in rows if r["status"] == "changed"),
                "added":   sum(1 for r in rows if r["status"] == "added"),
                "removed": sum(1 for r in rows if r["status"] == "removed"),
            },
        }

if __name__ == "__main__":
    uvicorn.run("deployment_diff:app", host="0.0.0.0", port=8158, reload=True)
