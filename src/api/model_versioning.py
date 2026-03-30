"""Model Versioning Service — OCI Robot Cloud (port 8162)
Semantic versioning system for GR00T fine-tuned models.
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

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

VERSIONS = [
    {
        "semver": "v0.1.0",
        "model": "bc_baseline",
        "date": "2026-01-10",
        "sr": 0.05,
        "breaking_change": False,
        "notes": "Initial behavioral cloning baseline",
        "major": 0,
    },
    {
        "semver": "v0.2.0",
        "model": "dagger_run5",
        "date": "2026-01-28",
        "sr": 0.42,
        "breaking_change": False,
        "notes": "DAgger online learning, 500 expert demos",
        "major": 0,
    },
    {
        "semver": "v0.3.0",
        "model": "dagger_run9_v2",
        "date": "2026-02-14",
        "sr": 0.71,
        "breaking_change": False,
        "notes": "DAgger run9 v2.2 production — chunk_size fix",
        "major": 0,
    },
    {
        "semver": "v0.3.1",
        "model": "dagger_run9_v2_hotfix",
        "date": "2026-02-20",
        "sr": 0.71,
        "breaking_change": False,
        "notes": "Patch: fixed gripper timing offset",
        "major": 0,
    },
    {
        "semver": "v1.0.0",
        "model": "groot_finetune_v2",
        "date": "2026-03-01",
        "sr": 0.78,
        "breaking_change": True,
        "notes": "MAJOR: GR00T N1.6 backbone upgrade, API v2",
        "major": 1,
    },
    {
        "semver": "v1.0.1",
        "model": "groot_finetune_v2_patch",
        "date": "2026-03-15",
        "sr": 0.78,
        "breaking_change": False,
        "notes": "Patch: reduced temperature 0.1\u21920.08",
        "major": 1,
    },
    {
        "semver": "v1.1.0-rc1",
        "model": "groot_finetune_v3",
        "date": "2026-03-30",
        "sr": None,
        "breaking_change": False,
        "notes": "RC: extended training 8k steps (in progress)",
        "major": 1,
    },
]

# Map date string -> x position for timeline (Jan 1 2026 = 0, Apr 1 2026 = 90 days)
DAY_ORIGIN = "2026-01-01"


def _days_from_origin(date_str: str) -> int:
    from datetime import date
    parts = date_str.split("-")
    d = date(int(parts[0]), int(parts[1]), int(parts[2]))
    origin_parts = DAY_ORIGIN.split("-")
    origin = date(int(origin_parts[0]), int(origin_parts[1]), int(origin_parts[2]))
    return (d - origin).days


def _is_rc(semver: str) -> bool:
    return "-rc" in semver.lower()


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _svg_timeline() -> str:
    """Horizontal timeline Jan-Apr 2026 with version circles."""
    W, H = 680, 160
    PAD_L, PAD_R = 60, 40
    AXIS_Y = 100
    TOTAL_DAYS = 89  # Jan 1 -> Apr 1

    def day_to_x(days: int) -> float:
        return PAD_L + (days / TOTAL_DAYS) * (W - PAD_L - PAD_R)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:monospace">')

    # Month tick marks and labels
    months = [("Jan", 0), ("Feb", 31), ("Mar", 59), ("Apr", 89)]
    for label, day in months:
        x = day_to_x(day)
        lines.append(f'<line x1="{x:.1f}" y1="{AXIS_Y}" x2="{x:.1f}" y2="{AXIS_Y+8}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{AXIS_Y+22}" fill="#94a3b8" font-size="11" text-anchor="middle">{label}</text>')

    # Main axis line
    lines.append(f'<line x1="{PAD_L}" y1="{AXIS_Y}" x2="{W-PAD_R}" y2="{AXIS_Y}" stroke="#334155" stroke-width="2"/>')

    # Version circles
    for v in VERSIONS:
        days = _days_from_origin(v["date"])
        x = day_to_x(days)
        rc = _is_rc(v["semver"])
        # Circle size proportional to SR (min 8, max 18); RC uses SR=0 -> size 8
        sr_val = v["sr"] if v["sr"] is not None else 0.0
        r = 8 + int(sr_val * 14)
        color = "#38bdf8" if v["major"] == 0 else "#C74634"
        if rc:
            lines.append(f'<circle cx="{x:.1f}" cy="{AXIS_Y}" r="{r}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="4 2"/>')
        else:
            lines.append(f'<circle cx="{x:.1f}" cy="{AXIS_Y}" r="{r}" fill="{color}" opacity="0.85"/>')

        # Version label above
        label_y = AXIS_Y - r - 6
        lines.append(f'<text x="{x:.1f}" y="{label_y:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{v["semver"]}</text>')

        # Breaking change lightning bolt marker
        if v["breaking_change"]:
            lines.append(f'<text x="{x:.1f}" y="{label_y - 12:.1f}" fill="#fbbf24" font-size="12" text-anchor="middle">\u26a1</text>')

    # Legend
    lines.append('<circle cx="30" cy="18" r="6" fill="#38bdf8" opacity="0.85"/>')
    lines.append('<text x="40" y="22" fill="#94a3b8" font-size="10">v0.x</text>')
    lines.append('<circle cx="80" cy="18" r="6" fill="#C74634" opacity="0.85"/>')
    lines.append('<text x="90" y="22" fill="#94a3b8" font-size="10">v1.x</text>')
    lines.append('<circle cx="135" cy="18" r="6" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="4 2"/>')
    lines.append('<text x="145" y="22" fill="#94a3b8" font-size="10">RC</text>')
    lines.append('<text x="180" y="22" fill="#fbbf24" font-size="12">\u26a1</text>')
    lines.append('<text x="195" y="22" fill="#94a3b8" font-size="10">Breaking</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _svg_sr_progression() -> str:
    """Line chart: success rate vs date with version tag annotations."""
    W, H = 680, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 30, 20, 40
    PLOT_W = W - PAD_L - PAD_R
    PLOT_H = H - PAD_T - PAD_B
    TOTAL_DAYS = 89

    def day_to_x(days: int) -> float:
        return PAD_L + (days / TOTAL_DAYS) * PLOT_W

    def sr_to_y(sr: float) -> float:
        return PAD_T + PLOT_H - (sr * PLOT_H)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:monospace">')

    # Y axis gridlines and labels
    for pct in [0, 25, 50, 75, 100]:
        y = sr_to_y(pct / 100)
        lines.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-5}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{pct}%</text>')

    # Axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+PLOT_H}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T+PLOT_H}" x2="{W-PAD_R}" y2="{PAD_T+PLOT_H}" stroke="#475569" stroke-width="1"/>')

    # Major version upgrade band (v0.3.1 -> v1.0.0)
    v_prev = next(v for v in VERSIONS if v["semver"] == "v0.3.1")
    v_major = next(v for v in VERSIONS if v["semver"] == "v1.0.0")
    x_band_l = day_to_x(_days_from_origin(v_prev["date"]))
    x_band_r = day_to_x(_days_from_origin(v_major["date"]))
    lines.append(f'<rect x="{x_band_l:.1f}" y="{PAD_T}" width="{x_band_r-x_band_l:.1f}" height="{PLOT_H}" fill="#C74634" opacity="0.08"/>')
    band_mid = (x_band_l + x_band_r) / 2
    lines.append(f'<text x="{band_mid:.1f}" y="{PAD_T+12:.1f}" fill="#C74634" font-size="9" text-anchor="middle" opacity="0.7">Major Upgrade</text>')

    # Line path — skip RC versions (sr=None)
    stable = [v for v in VERSIONS if v["sr"] is not None]
    pts = [(day_to_x(_days_from_origin(v["date"])), sr_to_y(v["sr"])) for v in stable]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lines.append(f'<path d="{path_d}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # Dots and version labels
    for i, v in enumerate(stable):
        x, y = pts[i]
        color = "#38bdf8" if v["major"] == 0 else "#C74634"
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        # Alternate label above/below to avoid overlap
        label_y = y - 10 if i % 2 == 0 else y + 18
        lines.append(f'<text x="{x:.1f}" y="{label_y:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{v["semver"]}</text>')

    # RC dot (dashed)
    rc_v = next((v for v in VERSIONS if _is_rc(v["semver"])), None)
    if rc_v:
        rx = day_to_x(_days_from_origin(rc_v["date"]))
        ry = sr_to_y(0.85)  # projected
        lines.append(f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="4" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="3 2"/>')
        lines.append(f'<text x="{rx:.1f}" y="{ry-10:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{rc_v["semver"]} (proj)</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    svg_timeline = _svg_timeline()
    svg_sr = _svg_sr_progression()

    rows = []
    for v in reversed(VERSIONS):
        major = v["major"]
        badge_color = "#38bdf8" if major == 0 else "#C74634"
        rc_tag = ' <span style="color:#fbbf24;font-size:10px">[RC]</span>' if _is_rc(v["semver"]) else ""
        bc_icon = '<span title="Breaking change" style="color:#fbbf24">\u26a1 Yes</span>' if v["breaking_change"] else '<span style="color:#64748b">No</span>'
        sr_str = f"{v['sr']*100:.0f}%" if v["sr"] is not None else '<span style="color:#64748b">TBD</span>'
        rows.append(f'''
        <tr style="border-bottom:1px solid #1e293b">
          <td><span style="background:{badge_color};color:#0f172a;padding:2px 7px;border-radius:4px;font-size:12px;font-weight:bold">{v["semver"]}</span>{rc_tag}</td>
          <td style="color:#94a3b8">{v["date"]}</td>
          <td style="color:#e2e8f0">{v["model"]}</td>
          <td style="color:#38bdf8;font-weight:bold">{sr_str}</td>
          <td>{bc_icon}</td>
          <td style="color:#94a3b8;font-size:12px">{v["notes"]}</td>
        </tr>''')

    rows_html = "".join(rows)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Model Versioning — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px }}
    h1 {{ color:#C74634; margin-bottom:4px }}
    .subtitle {{ color:#64748b; font-size:13px; margin-bottom:24px }}
    .card {{ background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:20px; margin-bottom:20px }}
    h2 {{ color:#38bdf8; font-size:15px; margin:0 0 14px }}
    table {{ width:100%; border-collapse:collapse }}
    th {{ color:#64748b; font-size:12px; text-align:left; padding:6px 10px; border-bottom:1px solid #1e293b }}
    td {{ padding:8px 10px; font-size:13px; vertical-align:middle }}
    tr:hover {{ background:#1e293b30 }}
    .pill {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px }}
  </style>
</head>
<body>
  <h1>Model Versioning Service</h1>
  <div class="subtitle">GR00T Fine-Tuned Model Registry &mdash; OCI Robot Cloud &mdash; port 8162</div>

  <div class="card">
    <h2>Version Timeline</h2>
    {svg_timeline}
  </div>

  <div class="card">
    <h2>Success Rate Progression</h2>
    {svg_sr}
  </div>

  <div class="card">
    <h2>Changelog</h2>
    <table>
      <thead>
        <tr>
          <th>Version</th><th>Date</th><th>Model</th><th>Success Rate</th><th>Breaking</th><th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <div style="color:#334155;font-size:11px;margin-top:8px">API endpoints: GET /versions &nbsp;|&nbsp; GET /latest &nbsp;|&nbsp; GET /changelog &nbsp;|&nbsp; GET /versions/{{semver}}</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Model Versioning Service", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/versions")
    def list_versions():
        return VERSIONS

    @app.get("/latest")
    def get_latest():
        """Return highest non-RC version."""
        stable = [v for v in VERSIONS if not _is_rc(v["semver"])]
        if not stable:
            raise HTTPException(status_code=404, detail="No stable versions found")
        return stable[-1]

    @app.get("/changelog")
    def changelog():
        return [{"semver": v["semver"], "date": v["date"], "notes": v["notes"], "breaking_change": v["breaking_change"]} for v in VERSIONS]

    @app.get("/versions/{semver}")
    def get_version(semver: str):
        match = next((v for v in VERSIONS if v["semver"] == semver), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"Version {semver!r} not found")
        return match

else:
    # Stub for environments without FastAPI installed
    class app:  # type: ignore
        pass


if __name__ == "__main__":
    if uvicorn is not None:
        uvicorn.run("model_versioning:app", host="0.0.0.0", port=8162, reload=False)
    else:
        print("uvicorn not installed — cannot start server")
