"""api_gateway_monitor.py
OCI Robot Cloud API gateway monitor — rate limiting, auth, and routing analytics.
Usage: python api_gateway_monitor.py
       uvicorn api_gateway_monitor:app --port 8186
Endpoints: GET / (dashboard), /keys, /endpoints, /summary, /throttle-events
"""
from __future__ import annotations
import json, math
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List

PORT: int = 8186

# ── Static data ──────────────────────────────────────────────────────────────

@dataclass
class APIKey:
    key_id: str
    partner: str
    tier: str
    rate_limit_per_min: int
    used_today: int
    quota_pct: float
    status: str

@dataclass
class EndpointStats:
    method: str
    path: str
    calls_24h: int
    avg_ms: float
    error_rate: float
    top_partner: str

API_KEYS: List[APIKey] = [
    APIKey("pi_prod_key",   "physical_intelligence", "enterprise", 1000, 12847, 21.4, "ACTIVE"),
    APIKey("apt_prod_key",  "apptronik",             "growth",      300,  3421, 19.0, "ACTIVE"),
    APIKey("onex_prod_key", "1x_technologies",       "starter",     100,   847, 14.1, "ACTIVE"),
    APIKey("agi_pilot_key", "agility_robotics",      "starter",     100,   312,  5.2, "ACTIVE"),
]

ENDPOINTS: List[EndpointStats] = [
    EndpointStats("POST", "/predict",     12847, 226.0,      0.002, "physical_intelligence"),
    EndpointStats("POST", "/finetune",       12, 14200000.0, 0.000, "physical_intelligence"),
    EndpointStats("GET",  "/eval/status",  4821,     12.0,  0.000, "apptronik"),
    EndpointStats("POST", "/dagger/step",  8420,    312.0,  0.006, "physical_intelligence"),
]

# Partner colours used in SVG charts
PARTNER_COLORS: Dict[str, str] = {
    "physical_intelligence": "#38bdf8",   # sky
    "apptronik":             "#f59e0b",   # amber
    "1x_technologies":       "#22c55e",   # green
    "agility_robotics":      "#a78bfa",   # purple
}

TIER_COLORS: Dict[str, str] = {
    "enterprise": "#C74634",
    "growth":     "#f59e0b",
    "starter":    "#38bdf8",
}

# Simulated 24-hour hourly call volumes per partner (index = hour 0-23)
def _hourly_volumes() -> Dict[str, List[int]]:
    """Synthetic hourly call volumes — peaks at business hours 9-17 PT."""
    base = [20, 15, 10, 8, 8, 12, 30, 80, 180, 320, 410, 480,
            460, 430, 390, 350, 290, 220, 160, 120, 90, 70, 50, 30]
    shares = {
        "physical_intelligence": 0.493,
        "apptronik":             0.131,
        "1x_technologies":       0.325,
        "agility_robotics":      0.012,
    }
    result: Dict[str, List[int]] = {}
    for partner, share in shares.items():
        result[partner] = [max(1, int(v * share)) for v in base]
    return result

HOURLY: Dict[str, List[int]] = _hourly_volumes()

# Simulated throttle events (last 24h)
THROTTLE_EVENTS = [
    {"ts": "2026-03-30T10:14:02Z", "key_id": "pi_prod_key",   "partner": "physical_intelligence", "endpoint": "/predict",      "burst_rpm": 1048, "action": "throttled"},
    {"ts": "2026-03-30T11:02:47Z", "key_id": "pi_prod_key",   "partner": "physical_intelligence", "endpoint": "/predict",      "burst_rpm": 1103, "action": "throttled"},
    {"ts": "2026-03-30T13:30:11Z", "key_id": "apt_prod_key",  "partner": "apptronik",             "endpoint": "/eval/status",  "burst_rpm":  312, "action": "throttled"},
    {"ts": "2026-03-30T15:45:59Z", "key_id": "pi_prod_key",   "partner": "physical_intelligence", "endpoint": "/dagger/step",  "burst_rpm": 1021, "action": "throttled"},
]

# ── SVG generators ────────────────────────────────────────────────────────────

def _svg_hourly_stacked(w: int = 680, h: int = 200) -> str:
    """Stacked area chart — 24h call volume by partner."""
    pad_l, pad_r, pad_t, pad_b = 48, 16, 16, 32
    cw = w - pad_l - pad_r
    ch = h - pad_t - pad_b
    partners = list(PARTNER_COLORS.keys())
    hours = list(range(24))

    # Stacked totals per hour
    stacked: List[List[int]] = []  # [hour][cumulative partner]
    for hr in hours:
        cum = 0
        row = []
        for p in partners:
            cum += HOURLY[p][hr]
            row.append(cum)
        stacked.append(row)

    max_val = max(stacked[hr][-1] for hr in hours)
    if max_val == 0:
        max_val = 1

    def x_pos(hr: int) -> float:
        return pad_l + hr * cw / 23

    def y_pos(val: float) -> float:
        return pad_t + ch - val * ch / max_val

    paths_svg = []
    # Draw areas from top partner down so lower partners render above
    for i in range(len(partners) - 1, -1, -1):
        color = PARTNER_COLORS[partners[i]]
        # Top edge of this partner's band
        pts_top = [(x_pos(hr), y_pos(stacked[hr][i])) for hr in hours]
        # Bottom edge: previous partner's cumulative (or 0)
        if i == 0:
            pts_bot = [(x_pos(hr), y_pos(0)) for hr in hours]
        else:
            pts_bot = [(x_pos(hr), y_pos(stacked[hr][i - 1])) for hr in hours]

        d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts_top)
        d += " L " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in reversed(pts_bot))
        d += " Z"
        paths_svg.append(f"<path d='{d}' fill='{color}' fill-opacity='0.75' stroke='{color}' stroke-width='1'/>")

    # X-axis labels every 4h
    x_labels = "".join(
        f"<text x='{x_pos(hr):.1f}' y='{h - 4}' fill='#94a3b8' font-size='9' text-anchor='middle'>{hr:02d}h</text>"
        for hr in range(0, 24, 4)
    )
    # Y-axis label
    y_label = f"<text x='10' y='{pad_t + ch // 2}' fill='#94a3b8' font-size='9' text-anchor='middle' transform='rotate(-90,10,{pad_t + ch // 2})'>calls</text>"
    # Y grid lines
    grid = "".join(
        f"<line x1='{pad_l}' y1='{y_pos(v):.1f}' x2='{pad_l + cw}' y2='{y_pos(v):.1f}' stroke='#1e293b' stroke-width='1'/>"
        f"<text x='{pad_l - 4}' y='{y_pos(v) + 3:.1f}' fill='#475569' font-size='8' text-anchor='end'>{v}</text>"
        for v in [0, max_val // 4, max_val // 2, 3 * max_val // 4, max_val]
    )
    # Legend
    legend_items = "".join(
        f"<rect x='{8 + idx * 160}' y='4' width='10' height='8' fill='{PARTNER_COLORS[p]}' fill-opacity='0.8'/>"
        f"<text x='{22 + idx * 160}' y='12' fill='#cbd5e1' font-size='9'>{p.replace('_', ' ')}</text>"
        for idx, p in enumerate(partners)
    )

    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
        f"style='background:#0f172a;border-radius:6px'>"
        f"{grid}{''.join(paths_svg)}{x_labels}{y_label}{legend_items}</svg>"
    )


def _svg_rate_limit_bars(w: int = 680, h: int = 160) -> str:
    """Horizontal bars — daily quota utilisation per API key."""
    pad_l, pad_r, pad_t, pad_b = 140, 80, 20, 20
    bar_h = 22
    bar_gap = 12
    cw = w - pad_l - pad_r

    bars_svg = []
    for idx, key in enumerate(API_KEYS):
        y = pad_t + idx * (bar_h + bar_gap)
        pct = min(key.quota_pct, 100.0)
        bar_w = pct * cw / 100
        color = PARTNER_COLORS.get(key.partner, "#64748b")
        if pct >= 80:
            color = "#f59e0b"
        if pct >= 100:
            color = "#ef4444"
        bars_svg.append(
            f"<rect x='{pad_l}' y='{y}' width='{cw}' height='{bar_h}' fill='#1e293b' rx='3'/>"
            f"<rect x='{pad_l}' y='{y}' width='{bar_w:.1f}' height='{bar_h}' fill='{color}' rx='3'/>"
            f"<text x='{pad_l - 8}' y='{y + bar_h // 2 + 4}' fill='#cbd5e1' font-size='10' text-anchor='end'>{key.key_id}</text>"
            f"<text x='{pad_l + bar_w + 6:.1f}' y='{y + bar_h // 2 + 4}' fill='#94a3b8' font-size='10'>{pct:.1f}%</text>"
        )

    total_h = pad_t + len(API_KEYS) * (bar_h + bar_gap) + pad_b
    # Threshold lines
    x80  = pad_l + 0.80 * cw
    x100 = pad_l + cw
    thresh = (
        f"<line x1='{x80:.1f}' y1='{pad_t - 10}' x2='{x80:.1f}' y2='{total_h - pad_b}' "
        f"stroke='#f59e0b' stroke-width='1' stroke-dasharray='4,3'/>"
        f"<text x='{x80:.1f}' y='{pad_t - 13}' fill='#f59e0b' font-size='8' text-anchor='middle'>80% warn</text>"
        f"<line x1='{x100:.1f}' y1='{pad_t - 10}' x2='{x100:.1f}' y2='{total_h - pad_b}' "
        f"stroke='#ef4444' stroke-width='1' stroke-dasharray='4,3'/>"
        f"<text x='{x100:.1f}' y='{pad_t - 13}' fill='#ef4444' font-size='8' text-anchor='middle'>100% throttle</text>"
    )

    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{total_h}' "
        f"style='background:#0f172a;border-radius:6px'>"
        f"{thresh}{''.join(bars_svg)}</svg>"
    )


# ── HTML dashboard builder ────────────────────────────────────────────────────

def _build_dashboard_html() -> str:
    total_calls  = sum(e.calls_24h for e in ENDPOINTS)
    total_errors = sum(int(e.calls_24h * e.error_rate) for e in ENDPOINTS)
    error_pct    = total_errors / total_calls * 100 if total_calls else 0

    stat_cards = "".join([
        _stat_card("Total API Calls (24h)",      f"{total_calls:,}",       "#38bdf8"),
        _stat_card("Authenticated",              "100%",                   "#22c55e"),
        _stat_card("Avg Gateway Overhead",       "1.2ms",                  "#a78bfa"),
        _stat_card("Errors",                     f"{total_errors} / {error_pct:.2f}%", "#f87171"),
    ])

    key_rows = "".join(
        f"<tr>"
        f"<td style='color:{PARTNER_COLORS.get(k.partner, '#888')}'>{k.partner}</td>"
        f"<td>{k.key_id}</td>"
        f"<td><span style='background:{TIER_COLORS.get(k.tier,'#334155')};color:#fff;"
        f"padding:2px 8px;border-radius:4px;font-size:11px'>{k.tier}</span></td>"
        f"<td>{k.rate_limit_per_min}/min</td>"
        f"<td>{k.used_today:,}</td>"
        f"<td>{k.quota_pct:.1f}%</td>"
        f"<td style='color:#22c55e'>{k.status}</td>"
        f"</tr>"
        for k in API_KEYS
    )

    ep_rows = "".join(
        f"<tr>"
        f"<td><span style='color:#38bdf8'>{e.method}</span> {e.path}</td>"
        f"<td>{e.calls_24h:,}</td>"
        f"<td>{e.avg_ms if e.avg_ms < 1000 else e.avg_ms/1000:.0f}{'ms' if e.avg_ms < 1000 else 's'}</td>"
        f"<td style='color:{"#f87171" if e.error_rate > 0 else "#22c55e"}'>{e.error_rate*100:.1f}%</td>"
        f"<td style='color:{PARTNER_COLORS.get(e.top_partner,"#888")}'>{e.top_partner}</td>"
        f"</tr>"
        for e in ENDPOINTS
    )

    throttle_rows = "".join(
        f"<tr><td>{ev['ts']}</td><td style='color:{PARTNER_COLORS.get(ev['partner'],'#888')}'>"
        f"{ev['partner']}</td><td>{ev['endpoint']}</td>"
        f"<td style='color:#f87171'>{ev['burst_rpm']} rpm</td>"
        f"<td style='color:#f59e0b'>{ev['action']}</td></tr>"
        for ev in THROTTLE_EVENTS
    )

    svg_hourly = _svg_hourly_stacked()
    svg_bars   = _svg_rate_limit_bars()

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset='UTF-8'/>
  <title>OCI Robot Cloud — API Gateway Monitor</title>
  <style>
    body   {{ background:#0f172a; color:#e2e8f0; font-family:monospace; padding:24px; margin:0 }}
    h1     {{ color:#C74634; margin-bottom:4px }}
    h2     {{ color:#38bdf8; font-size:14px; margin:24px 0 8px }}
    .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0 }}
    .card  {{ background:#1e293b; border-radius:8px; padding:14px 20px; min-width:140px }}
    .card .val {{ font-size:22px; font-weight:bold; color:#f8fafc }}
    .card .lbl {{ font-size:11px; color:#64748b; margin-top:4px }}
    table  {{ border-collapse:collapse; width:100%; margin-bottom:16px }}
    th     {{ background:#1e293b; color:#C74634; padding:8px 10px; text-align:left; font-size:12px }}
    td     {{ padding:6px 10px; border-bottom:1px solid #1e293b; font-size:12px }}
    tr:hover td {{ background:#1a2744 }}
    footer {{ color:#334155; font-size:11px; margin-top:28px }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — API Gateway Monitor</h1>
  <p style='color:#64748b;font-size:12px'>Port {PORT} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | 4 active keys</p>

  <div class='cards'>{stat_cards}</div>

  <h2>Hourly API Call Volume (24h) — Stacked by Partner</h2>
  {svg_hourly}

  <h2>Rate Limit Utilisation — Daily Quota</h2>
  {svg_bars}

  <h2>API Keys</h2>
  <table>
    <tr><th>Partner</th><th>Key ID</th><th>Tier</th><th>Rate Limit</th><th>Used Today</th><th>Quota %</th><th>Status</th></tr>
    {key_rows}
  </table>

  <h2>Endpoint Traffic (24h)</h2>
  <table>
    <tr><th>Endpoint</th><th>Calls</th><th>Avg Latency</th><th>Error Rate</th><th>Top Partner</th></tr>
    {ep_rows}
  </table>

  <h2>Throttle Events (24h)</h2>
  <table>
    <tr><th>Timestamp</th><th>Partner</th><th>Endpoint</th><th>Burst RPM</th><th>Action</th></tr>
    {throttle_rows}
  </table>

  <footer>Oracle Cloud Infrastructure | OCI Robot Cloud | api_gateway_monitor.py | Port {PORT}</footer>
</body>
</html>"""


def _stat_card(label: str, value: str, color: str) -> str:
    return (
        f"<div class='card'>"
        f"<div class='val' style='color:{color}'>{value}</div>"
        f"<div class='lbl'>{label}</div>"
        f"</div>"
    )


# ── FastAPI app ───────────────────────────────────────────────────────────────

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(
        title="OCI Robot Cloud — API Gateway Monitor",
        version="1.0.0",
        description="Rate limiting, auth, and routing analytics for OCI Robot Cloud.",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return _build_dashboard_html()

    @app.get("/keys")
    def get_keys():
        return JSONResponse([asdict(k) for k in API_KEYS])

    @app.get("/endpoints")
    def get_endpoints():
        return JSONResponse([asdict(e) for e in ENDPOINTS])

    @app.get("/summary")
    def get_summary():
        total_calls  = sum(e.calls_24h for e in ENDPOINTS)
        total_errors = sum(int(e.calls_24h * e.error_rate) for e in ENDPOINTS)
        return JSONResponse({
            "total_calls_24h":       total_calls,
            "authenticated_pct":     100.0,
            "avg_gateway_overhead_ms": 1.2,
            "total_errors":          total_errors,
            "error_rate_pct":        round(total_errors / total_calls * 100, 4) if total_calls else 0,
            "active_keys":           len(API_KEYS),
            "throttle_events_24h":   len(THROTTLE_EVENTS),
        })

    @app.get("/throttle-events")
    def get_throttle_events():
        return JSONResponse(THROTTLE_EVENTS)

except ImportError:
    app = None


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    sep = "=" * 72
    print(sep)
    print("OCI Robot Cloud — API Gateway Monitor")
    print(f"Port {PORT}  |  4 API keys  |  4 endpoints")
    print(sep)

    total_calls  = sum(e.calls_24h for e in ENDPOINTS)
    total_errors = sum(int(e.calls_24h * e.error_rate) for e in ENDPOINTS)
    print(f"\nTotal API calls (24h): {total_calls:,}")
    print(f"Errors: {total_errors} ({total_errors/total_calls*100:.2f}%)")
    print(f"Avg gateway overhead: 1.2ms | Auth rate: 100%")

    print(f"\n{'Key ID':<20} {'Partner':<26} {'Tier':<12} {'Used Today':>10} {'Quota%':>8}")
    print("-" * 72)
    for k in API_KEYS:
        print(f"{k.key_id:<20} {k.partner:<26} {k.tier:<12} {k.used_today:>10,} {k.quota_pct:>7.1f}%")

    print(f"\n{'Endpoint':<28} {'Calls':>8} {'Avg ms':>10} {'Err%':>7}")
    print("-" * 72)
    for e in ENDPOINTS:
        avg_str = f"{e.avg_ms:.0f}ms" if e.avg_ms < 1000 else f"{e.avg_ms/1000:.0f}s"
        print(f"{e.method+' '+e.path:<28} {e.calls_24h:>8,} {avg_str:>10} {e.error_rate*100:>6.1f}%")

    print(f"\nThrottle events (24h): {len(THROTTLE_EVENTS)}")
    for ev in THROTTLE_EVENTS:
        print(f"  {ev['ts']}  {ev['partner']:<26} {ev['endpoint']:<16} {ev['burst_rpm']} rpm → {ev['action']}")
    print(sep)


if __name__ == "__main__":
    main()
