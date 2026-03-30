"""NVIDIA Robotics Ecosystem Integration Status Tracker — port 8168"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

import math
from datetime import datetime

COMPONENTS = [
    {
        "id": "groot_n1_6",
        "name": "GR00T N1.6",
        "version": "1.6",
        "status": "INTEGRATED",
        "integration_level": "FULL",
        "our_usage": "Fine-tuning backbone",
        "perf_gain": "8.7× MAE improvement",
        "last_updated": "2026-03-01",
    },
    {
        "id": "isaac_sim",
        "name": "Isaac Sim",
        "version": "4.5",
        "status": "INTEGRATED",
        "integration_level": "PARTIAL",
        "our_usage": "SDG scene generation",
        "perf_gain": "2000 demos/2.4h",
        "last_updated": "2026-02-15",
    },
    {
        "id": "cosmos_world_model",
        "name": "Cosmos World Model",
        "version": "1.0",
        "status": "INTEGRATED",
        "integration_level": "PARTIAL",
        "our_usage": "Physics-based world gen",
        "perf_gain": "30% domain diversity",
        "last_updated": "2026-03-10",
    },
    {
        "id": "isaac_lab",
        "name": "Isaac Lab",
        "version": "2.0",
        "status": "PLANNED",
        "integration_level": "NONE",
        "our_usage": "Target: RL environment wrapper",
        "perf_gain": "est +5pp SR",
        "last_updated": None,
    },
    {
        "id": "jetson_agx_orin",
        "name": "Jetson AGX Orin",
        "version": "JP6.1",
        "status": "INTEGRATED",
        "integration_level": "PARTIAL",
        "our_usage": "Edge deployment target",
        "perf_gain": "45ms inference (student model)",
        "last_updated": "2026-03-20",
    },
    {
        "id": "triton_inference_server",
        "name": "Triton Inference Server",
        "version": "2.44",
        "status": "PLANNED",
        "integration_level": "NONE",
        "our_usage": "Target: production serving",
        "perf_gain": "est 2× throughput",
        "last_updated": None,
    },
]

PARTNER_OPPORTUNITY = (
    "Preferred cloud agreement would give OCI pre-release access to "
    "GR00T N2 + Isaac Sim 5.0"
)


def _level_color(level: str) -> str:
    return {"FULL": "#22c55e", "PARTIAL": "#f59e0b", "NONE": "#6b7280"}[level]


def _status_badge_color(status: str) -> str:
    return {
        "INTEGRATED": "#22c55e",
        "PLANNED": "#6b7280",
        "IN_PROGRESS": "#38bdf8",
    }.get(status, "#6b7280")


def _integration_progress_svg() -> str:
    """Horizontal bar per component showing 0/partial/full integration."""
    W, H = 680, 200
    n = len(COMPONENTS)
    row_h = (H - 40) // n
    label_w = 160
    bar_w = W - label_w - 40

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<text x="{label_w + bar_w // 2}" y="20" fill="#94a3b8" '
        f'font-size="11" text-anchor="middle" font-family="monospace">'
        f'Integration Level</text>',
    ]

    level_fill = {"FULL": bar_w, "PARTIAL": int(bar_w * 0.5), "NONE": 0}

    for i, c in enumerate(COMPONENTS):
        y = 30 + i * row_h
        cx = label_w + 4
        fill_w = level_fill[c["integration_level"]]
        is_planned = c["status"] == "PLANNED"
        bar_color = _level_color(c["integration_level"])

        # label
        lines.append(
            f'<text x="{label_w - 6}" y="{y + row_h // 2 + 4}" fill="#e2e8f0" '
            f'font-size="10" text-anchor="end" font-family="monospace">{c["name"]}</text>'
        )
        # background track
        lines.append(
            f'<rect x="{cx}" y="{y + 4}" width="{bar_w}" height="{row_h - 12}" '
            f'rx="3" fill="#334155"/>'
        )
        if is_planned:
            # dashed outline, no fill
            lines.append(
                f'<rect x="{cx}" y="{y + 4}" width="{bar_w}" height="{row_h - 12}" '
                f'rx="3" fill="none" stroke="#6b7280" stroke-width="1.5" '
                f'stroke-dasharray="6,4"/>'
            )
        elif fill_w > 0:
            lines.append(
                f'<rect x="{cx}" y="{y + 4}" width="{fill_w}" height="{row_h - 12}" '
                f'rx="3" fill="{bar_color}"/>'
            )
        # label inside bar
        lvl_label = c["integration_level"]
        lines.append(
            f'<text x="{cx + 6}" y="{y + row_h // 2 + 4}" fill="#0f172a" '
            f'font-size="9" font-family="monospace" font-weight="bold">{lvl_label}</text>'
        )

    # legend
    lx = label_w + 4
    ly = H - 12
    for color, label in [("#22c55e", "FULL"), ("#f59e0b", "PARTIAL"), ("#6b7280", "NONE/PLANNED")]:
        lines.append(
            f'<rect x="{lx}" y="{ly - 8}" width="10" height="8" fill="{color}" rx="2"/>'
        )
        lines.append(
            f'<text x="{lx + 13}" y="{ly}" fill="#94a3b8" font-size="9" '
            f'font-family="monospace">{label}</text>'
        )
        lx += 100

    lines.append("</svg>")
    return "\n".join(lines)


def _dependency_graph_svg() -> str:
    """Nodes + edges showing data flow between NVIDIA components and OCI Robot Cloud."""
    W, H = 600, 280

    # positions: center = OCI Robot Cloud; periphery = NVIDIA components
    cx, cy = W // 2, H // 2
    r = 100
    angles = [math.pi * (0.5 + 2 * i / 6) for i in range(6)]

    node_pos = {c["id"]: (int(cx + r * math.cos(a)), int(cy + r * math.sin(a)))
                for c, a in zip(COMPONENTS, angles)}
    node_pos["oci_robot_cloud"] = (cx, cy)

    edges = [
        ("groot_n1_6", "oci_robot_cloud", "finetune"),
        ("isaac_sim", "oci_robot_cloud", "SDG"),
        ("cosmos_world_model", "oci_robot_cloud", "domain_rand"),
        ("oci_robot_cloud", "jetson_agx_orin", "deploy"),
        ("oci_robot_cloud", "triton_inference_server", "serve"),
        ("isaac_lab", "oci_robot_cloud", "RL env"),
    ]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
        '<defs><marker id="arr" markerWidth="6" markerHeight="4" refX="6" refY="2" '
        'orient="auto"><polygon points="0 0, 6 2, 0 4" fill="#38bdf8"/></marker></defs>',
    ]

    # edges
    for src, dst, label in edges:
        x1, y1 = node_pos[src]
        x2, y2 = node_pos[dst]
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#38bdf8" stroke-width="1.2" stroke-opacity="0.6" '
            f'marker-end="url(#arr)"/>'
        )
        lines.append(
            f'<text x="{mx}" y="{my - 3}" fill="#94a3b8" font-size="8" '
            f'text-anchor="middle" font-family="monospace">{label}</text>'
        )

    # NVIDIA component nodes
    for c in COMPONENTS:
        x, y = node_pos[c["id"]]
        color = _level_color(c["integration_level"])
        lines.append(
            f'<circle cx="{x}" cy="{y}" r="22" fill="#0f172a" '
            f'stroke="{color}" stroke-width="2"/>'
        )
        short = c["name"].replace("Isaac ", "I.").replace(" World Model", "")
        lines.append(
            f'<text x="{x}" y="{y + 3}" fill="#e2e8f0" font-size="7" '
            f'text-anchor="middle" font-family="monospace">{short}</text>'
        )

    # OCI center node
    lines.append(
        f'<circle cx="{cx}" cy="{cy}" r="30" fill="#C74634" stroke="#f87171" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{cx}" y="{cy - 4}" fill="white" font-size="8" '
        f'text-anchor="middle" font-family="monospace" font-weight="bold">OCI Robot</text>'
    )
    lines.append(
        f'<text x="{cx}" y="{cy + 7}" fill="white" font-size="8" '
        f'text-anchor="middle" font-family="monospace" font-weight="bold">Cloud</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


def _html_dashboard() -> str:
    progress_svg = _integration_progress_svg()
    dep_svg = _dependency_graph_svg()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    rows = ""
    for c in COMPONENTS:
        badge_color = _status_badge_color(c["status"])
        level_color = _level_color(c["integration_level"])
        updated = c["last_updated"] or "—"
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600;color:#e2e8f0">{c['name']}</td>
          <td style="padding:8px 12px;color:#94a3b8">{c['version']}</td>
          <td style="padding:8px 12px">
            <span style="background:{badge_color};color:#0f172a;padding:2px 8px;
              border-radius:10px;font-size:11px;font-weight:700">{c['status']}</span>
          </td>
          <td style="padding:8px 12px">
            <span style="color:{level_color};font-weight:600">{c['integration_level']}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{c['our_usage']}</td>
          <td style="padding:8px 12px;color:#38bdf8">{c['perf_gain']}</td>
          <td style="padding:8px 12px;color:#64748b">{updated}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>NVIDIA Ecosystem Tracker — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px; }}
    h1 {{ color:#C74634; margin:0 0 4px; font-size:22px; }}
    h2 {{ color:#38bdf8; font-size:15px; margin:24px 0 10px; }}
    .subtitle {{ color:#64748b; font-size:12px; margin-bottom:24px; }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px; overflow:hidden; }}
    th {{ background:#0f172a; color:#64748b; font-size:11px; padding:8px 12px; text-align:left; }}
    tr:hover td {{ background:#1e293b; }}
    .opportunity {{ background:#1e293b; border-left:3px solid #C74634; padding:12px 16px;
      border-radius:0 8px 8px 0; margin:16px 0; color:#fbbf24; font-size:13px; }}
    .charts {{ display:flex; gap:20px; flex-wrap:wrap; margin:16px 0; }}
    .endpoints {{ background:#1e293b; border-radius:8px; padding:16px; margin-top:24px; }}
    .ep {{ color:#38bdf8; font-size:12px; margin:4px 0; }}
  </style>
</head>
<body>
  <h1>NVIDIA Ecosystem Tracker</h1>
  <div class="subtitle">OCI Robot Cloud · Integration Status · {today}</div>

  <div class="opportunity">Partner Opportunity: {PARTNER_OPPORTUNITY}</div>

  <h2>Integration Progress</h2>
  <div class="charts">
    {progress_svg}
  </div>

  <h2>Technology Dependency Graph</h2>
  <div class="charts">
    {dep_svg}
  </div>

  <h2>Component Status</h2>
  <table>
    <thead><tr>
      <th>Component</th><th>Version</th><th>Status</th>
      <th>Level</th><th>Our Usage</th><th>Perf Gain</th><th>Updated</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <div class="endpoints">
    <div style="color:#64748b;font-size:11px;margin-bottom:8px">ENDPOINTS</div>
    <div class="ep">GET /              — this dashboard</div>
    <div class="ep">GET /components    — all component data (JSON)</div>
    <div class="ep">GET /integration-status — summary counts (JSON)</div>
    <div class="ep">GET /roadmap       — planned integrations (JSON)</div>
  </div>
</body>
</html>"""


if FastAPI is not None:
    app = FastAPI(title="NVIDIA Ecosystem Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/components")
    def get_components():
        return {"components": COMPONENTS, "total": len(COMPONENTS)}

    @app.get("/integration-status")
    def integration_status():
        counts = {"FULL": 0, "PARTIAL": 0, "NONE": 0}
        statuses = {"INTEGRATED": 0, "PLANNED": 0}
        for c in COMPONENTS:
            counts[c["integration_level"]] += 1
            statuses[c["status"]] = statuses.get(c["status"], 0) + 1
        return {
            "integration_levels": counts,
            "statuses": statuses,
            "partner_opportunity": PARTNER_OPPORTUNITY,
            "last_refreshed": datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/roadmap")
    def roadmap():
        planned = [c for c in COMPONENTS if c["status"] == "PLANNED"]
        return {
            "planned_integrations": planned,
            "next_milestone": planned[0] if planned else None,
        }


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("nvidia_ecosystem_tracker:app", host="0.0.0.0", port=8168, reload=True)
