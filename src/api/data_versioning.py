"""Data Versioning — FastAPI port 8205

Dataset version control: track dataset evolution and provenance across the
OCI Robot Cloud training pipeline.
"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTTPException = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

from typing import Optional

# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------

DATASETS = [
    {
        "id": "ds_v1.0",
        "name": "genesis_sdg_v1",
        "demos": 500,
        "size_gb": 2.4,
        "created": "2026-01-08",
        "parent": None,
        "sr_after_train": 0.31,
        "status": "ARCHIVED",
    },
    {
        "id": "ds_v1.1",
        "name": "genesis_sdg_v2",
        "demos": 1000,
        "size_gb": 4.9,
        "created": "2026-01-20",
        "parent": "ds_v1.0",
        "sr_after_train": 0.42,
        "status": "ARCHIVED",
    },
    {
        "id": "ds_v2.0",
        "name": "genesis_sdg_v3_raw",
        "demos": 2000,
        "size_gb": 9.8,
        "created": "2026-02-10",
        "parent": "ds_v1.1",
        "sr_after_train": None,
        "status": "ARCHIVED",
    },
    {
        "id": "ds_v2.1",
        "name": "genesis_sdg_v3_curated",
        "demos": 1600,
        "size_gb": 7.8,
        "created": "2026-02-14",
        "parent": "ds_v2.0",
        "sr_after_train": 0.64,
        "status": "ARCHIVED",
    },
    {
        "id": "ds_v3.0",
        "name": "dagger_run9_collected",
        "demos": 1000,
        "size_gb": 4.8,
        "created": "2026-02-28",
        "parent": None,
        "sr_after_train": 0.71,
        "status": "ACTIVE",
    },
    {
        "id": "ds_v3.1",
        "name": "combined_v3_plus_dagger",
        "demos": 2600,
        "size_gb": 12.6,
        "created": "2026-03-01",
        "parent": "ds_v2.1+ds_v3.0",
        "sr_after_train": 0.78,
        "status": "PRODUCTION",
    },
    {
        "id": "ds_v4.0",
        "name": "real_robot_pi_v1",
        "demos": 58,
        "size_gb": 0.28,
        "created": "2026-03-30",
        "parent": None,
        "sr_after_train": None,
        "status": "COLLECTING",
    },
    {
        "id": "ds_v4.1",
        "name": "combined_v3_plus_real",
        "demos": 2658,
        "size_gb": 12.88,
        "created": None,
        "parent": "ds_v3.1+ds_v4.0",
        "sr_after_train": None,
        "status": "PLANNED",
    },
]

DS_BY_ID = {d["id"]: d for d in DATASETS}

# ---------------------------------------------------------------------------
# SVG: Dataset evolution DAG  680x280
# ---------------------------------------------------------------------------

# Node layout (id -> cx, cy)
NODE_POS = {
    "ds_v1.0": (80, 60),
    "ds_v1.1": (80, 120),
    "ds_v2.0": (80, 180),
    "ds_v2.1": (80, 240),
    "ds_v3.0": (300, 180),
    "ds_v3.1": (300, 240),
    "ds_v4.0": (520, 180),
    "ds_v4.1": (520, 240),
}


def _node_color(ds: dict) -> str:
    sr = ds["sr_after_train"]
    if sr is None:
        return "#475569"
    if sr >= 0.70:
        return "#22c55e"
    if sr >= 0.50:
        return "#38bdf8"
    return "#f59e0b"


def _node_r(ds: dict) -> int:
    demos = ds["demos"]
    # Scale radius 10-28 over range 58-2658
    lo, hi = 58, 2658
    ratio = (demos - lo) / (hi - lo)
    return int(10 + ratio * 18)


def _svg_dag() -> str:
    W, H = 680, 280

    # Draw edges first
    edges = []
    for ds in DATASETS:
        if ds["parent"] is None:
            continue
        parents = ds["parent"].split("+")
        dst = NODE_POS[ds["id"]]
        for pid in parents:
            if pid in NODE_POS:
                src = NODE_POS[pid]
                dashed = 'stroke-dasharray="6,4"' if ds["status"] == "PLANNED" else ""
                edges.append(
                    f'<line x1="{src[0]}" y1="{src[1]}" x2="{dst[0]}" y2="{dst[1]}" '
                    f'stroke="#475569" stroke-width="1.5" {dashed}/>'
                )

    # Arrowhead marker
    marker = """<defs>
    <marker id="arr" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#475569"/>
    </marker>
  </defs>"""

    # Draw nodes
    nodes = []
    for ds in DATASETS:
        cx, cy = NODE_POS[ds["id"]]
        r = _node_r(ds)
        color = _node_color(ds)
        stroke = "#f1f5f9" if ds["status"] == "PRODUCTION" else "#334155"
        sw = 2 if ds["status"] == "PRODUCTION" else 1
        dash = 'stroke-dasharray="4,3"' if ds["status"] == "PLANNED" else ""
        nodes.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="{stroke}" stroke-width="{sw}" {dash} opacity="0.9"/>'
        )
        # Label above node
        label = ds["id"]
        nodes.append(
            f'<text x="{cx}" y="{cy - r - 4}" fill="#cbd5e1" font-size="8.5" text-anchor="middle">{label}</text>'
        )
        # SR label inside node if available
        if ds["sr_after_train"] is not None:
            nodes.append(
                f'<text x="{cx}" y="{cy + 3}" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">{ds["sr_after_train"]:.0%}</text>'
            )

    # Status legend
    legend_items = [
        ("#22c55e", "SR ≥ 0.70"),
        ("#38bdf8", "SR 0.50-0.70"),
        ("#f59e0b", "SR < 0.50"),
        ("#475569", "SR unknown"),
    ]
    legend = ""
    for i, (c, label) in enumerate(legend_items):
        lx = W - 130
        ly = 20 + i * 16
        legend += f'<circle cx="{lx}" cy="{ly}" r="5" fill="{c}"/>'
        legend += f'<text x="{lx + 10}" y="{ly + 4}" fill="#94a3b8" font-size="9">{label}</text>'

    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="6"/>
  {marker}
  {''.join(edges)}
  {''.join(nodes)}
  {legend}
</svg>"""


# ---------------------------------------------------------------------------
# SVG: SR progression line  680x180
# ---------------------------------------------------------------------------

def _svg_sr_progression() -> str:
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 20, 40
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    # Only datasets with SR
    pts_data = [(ds["id"], ds["sr_after_train"]) for ds in DATASETS if ds["sr_after_train"] is not None]
    n = len(pts_data)

    def xp(i):
        return PAD_L + (i / (n - 1)) * plot_w

    def yp(v):
        lo, hi = 0.20, 1.0
        return PAD_T + plot_h - ((v - lo) / (hi - lo)) * plot_h

    # Line
    polyline_pts = " ".join(f"{xp(i):.1f},{yp(v):.1f}" for i, (_, v) in enumerate(pts_data))

    # Circles + labels
    circles = ""
    for i, (did, v) in enumerate(pts_data):
        x = xp(i)
        y = yp(v)
        circles += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8" stroke="#0f172a" stroke-width="1"/>'
        circles += f'<text x="{x:.1f}" y="{y - 8:.1f}" fill="#38bdf8" font-size="8" text-anchor="middle">{v:.0%}</text>'
        circles += f'<text x="{x:.1f}" y="{H - 6}" fill="#94a3b8" font-size="8" text-anchor="middle">{did}</text>'

    # Y axis labels
    y_labels = "".join(
        f'<text x="{PAD_L - 6}" y="{yp(v):.1f}" fill="#94a3b8" font-size="9" text-anchor="end" dominant-baseline="middle">{v:.1f}</text>'
        for v in [0.2, 0.4, 0.6, 0.8, 1.0]
    )

    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="6"/>
  <polyline points="{polyline_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  {circles}
  <line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>
  <line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{W - PAD_R}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>
  {y_labels}
</svg>"""


# ---------------------------------------------------------------------------
# Lineage table HTML rows
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "PRODUCTION": ("#166534", "#22c55e"),
    "ACTIVE": ("#1e3a5f", "#38bdf8"),
    "COLLECTING": ("#713f12", "#f59e0b"),
    "ARCHIVED": ("#374151", "#9ca3af"),
    "PLANNED": ("#4a1d96", "#a78bfa"),
}


def _lineage_rows() -> str:
    rows = []
    for ds in DATASETS:
        bg, fg = STATUS_COLORS.get(ds["status"], ("#374151", "#9ca3af"))
        sr_str = f"{ds['sr_after_train']:.0%}" if ds["sr_after_train"] is not None else "—"
        parent_str = ds["parent"] or "—"
        created_str = ds["created"] or "pending"
        rows.append(
            f"""<tr>
  <td style="color:#f1f5f9;font-weight:600;">{ds['id']}</td>
  <td style="color:#cbd5e1;">{ds['name']}</td>
  <td style="text-align:right;">{ds['demos']:,}</td>
  <td style="text-align:right;">{ds['size_gb']} GB</td>
  <td style="color:#94a3b8;">{parent_str}</td>
  <td style="color:#94a3b8;">{created_str}</td>
  <td style="text-align:right;color:#38bdf8;font-weight:600;">{sr_str}</td>
  <td><span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;font-size:0.75rem;">{ds['status']}</span></td>
</tr>"""
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    dag_svg = _svg_dag()
    sr_svg = _svg_sr_progression()
    rows = _lineage_rows()

    production_ds = next((d for d in DATASETS if d["status"] == "PRODUCTION"), None)
    prod_info = ""
    if production_ds:
        prod_info = f"""
      <div style="background:#1e293b;border:2px solid #22c55e;border-radius:10px;padding:18px;">
        <div style="font-size:0.85rem;color:#22c55e;margin-bottom:8px;">PRODUCTION DATASET</div>
        <div style="font-size:1.2rem;font-weight:700;color:#f1f5f9;">{production_ds['id']} — {production_ds['name']}</div>
        <div style="display:flex;gap:24px;margin-top:10px;">
          <div><span style="color:#94a3b8;">Demos:</span> <strong style="color:#f1f5f9;">{production_ds['demos']:,}</strong></div>
          <div><span style="color:#94a3b8;">Size:</span> <strong style="color:#f1f5f9;">{production_ds['size_gb']} GB</strong></div>
          <div><span style="color:#94a3b8;">SR:</span> <strong style="color:#22c55e;">{production_ds['sr_after_train']:.0%}</strong></div>
          <div><span style="color:#94a3b8;">Created:</span> <strong style="color:#f1f5f9;">{production_ds['created']}</strong></div>
        </div>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Data Versioning — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 28px; }}
    h1 {{ font-size: 1.6rem; color: #f1f5f9; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }}
    .accent {{ color: #C74634; font-weight: 700; }}
    .section {{ margin-bottom: 28px; }}
    .section-title {{ font-size: 1rem; color: #38bdf8; font-weight: 600; margin-bottom: 12px;
                      border-bottom: 1px solid #334155; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
    th {{ background: #1e293b; color: #94a3b8; padding: 8px 10px; text-align: left;
          font-weight: 600; border-bottom: 1px solid #334155; }}
    td {{ padding: 7px 10px; border-bottom: 1px solid #1e293b; vertical-align: middle; }}
    tr:hover td {{ background: #1e293b; }}
  </style>
</head>
<body>
  <h1>Data Versioning <span class="accent">OCI Robot Cloud</span></h1>
  <p class="subtitle">Port 8205 &nbsp;·&nbsp; DVC-style dataset provenance tracking &nbsp;·&nbsp; 2026-03-30</p>

  <div class="section">
    {prod_info}
  </div>

  <div class="section">
    <div class="section-title">Dataset Evolution DAG</div>
    {dag_svg}
  </div>

  <div class="section">
    <div class="section-title">Success Rate Progression (post-training SR per dataset version)</div>
    {sr_svg}
  </div>

  <div class="section">
    <div class="section-title">Full Dataset Lineage</div>
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Name</th><th style="text-align:right;">Demos</th>
          <th style="text-align:right;">Size</th><th>Parent(s)</th>
          <th>Created</th><th style="text-align:right;">SR</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="Data Versioning",
        description="Dataset version control and provenance tracking",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        """Dataset versioning dashboard."""
        return _dashboard_html()

    @app.get("/datasets")
    def list_datasets():
        """All dataset versions."""
        return {"datasets": DATASETS, "count": len(DATASETS)}

    @app.get("/datasets/{dataset_id}")
    def get_dataset(dataset_id: str):
        """Single dataset version details."""
        ds = DS_BY_ID.get(dataset_id)
        if ds is None:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id!r} not found")
        return ds

    @app.get("/lineage")
    def lineage_dag():
        """Full dataset lineage as a DAG (adjacency list)."""
        edges = []
        for ds in DATASETS:
            if ds["parent"]:
                for pid in ds["parent"].split("+"):
                    edges.append({"from": pid.strip(), "to": ds["id"]})
        return {
            "nodes": [{"id": d["id"], "name": d["name"], "status": d["status"]} for d in DATASETS],
            "edges": edges,
        }

    @app.get("/current")
    def current_production():
        """Current PRODUCTION dataset."""
        ds = next((d for d in DATASETS if d["status"] == "PRODUCTION"), None)
        if ds is None:
            raise HTTPException(status_code=404, detail="No PRODUCTION dataset found")
        return ds


if __name__ == "__main__":
    if uvicorn is not None:
        uvicorn.run("data_versioning:app", host="0.0.0.0", port=8205, reload=True)
    else:
        print("uvicorn not installed — run: pip install uvicorn fastapi")
