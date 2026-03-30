import math
import random
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

SERVICE_TITLE = "Growth Marketing Dashboard"
PORT = 8965

METRICS = {
    "github_stars": 847,
    "github_contributors": 23,
    "discord_members": 312,
    "newsletter_subs": 1247,
    "newsletter_growth_pct": 28,
    "gtc_talk_views": 2000,
    "gtc_leads": 47,
    "blog_posts": 14,
    "blog_traffic": 8340,
    "seo_keywords": 63,
    "seo_rank_top10": 18,
    "conference_pipeline": 4,
}

CONTENT_ITEMS = [
    {"type": "GTC Talk", "title": "Fine-Tuning Robot Policies at Scale on OCI", "views": 2000, "leads": 47, "roi": "2,350%"},
    {"type": "Blog Post", "title": "MAE 0.013: How We Got 8.7x Better with IK SDG", "views": 1840, "leads": 23, "roi": "1,840%"},
    {"type": "Demo Video", "title": "UR5e Pick & Place with GR00T N1.6", "views": 3210, "leads": 31, "roi": "3,100%"},
    {"type": "GitHub README", "title": "OCI Robot Cloud — Full Stack Setup Guide", "views": 5400, "leads": 19, "roi": "950%"},
    {"type": "Newsletter", "title": "Weekly Robotics AI Digest (1,247 subscribers)", "views": 1247, "leads": 38, "roi": "3,800%"},
    {"type": "CoRL Paper", "title": "Cloud-Native Fine-Tuning for Embodied AI", "views": 620, "leads": 14, "roi": "700%"},
]

CONFERENCES = [
    {"name": "ICRA 2026", "date": "May 2026", "type": "Paper + Demo", "expected_leads": 35, "status": "confirmed"},
    {"name": "RSS 2026", "date": "Jul 2026", "type": "Workshop", "expected_leads": 28, "status": "submitted"},
    {"name": "CoRL 2026", "date": "Nov 2026", "type": "Paper", "expected_leads": 42, "status": "planned"},
    {"name": "ROSCon 2026", "date": "Oct 2026", "type": "Talk + SDK Demo", "expected_leads": 55, "status": "planned"},
]


def build_community_svg():
    """Community growth chart — GitHub stars, newsletter, Discord over 8 months."""
    months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    # Growth curves with compounding 28%/mo for newsletter
    newsletter = [int(1247 / (1.28 ** (7 - i))) for i in range(8)]
    stars = [int(847 * (0.55 + 0.45 * i / 7)) for i in range(8)]
    discord = [int(312 * (0.40 + 0.60 * i / 7)) for i in range(8)]

    w, h = 560, 210
    pad_l, pad_r, pad_t, pad_b = 55, 20, 24, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    max_val = max(max(newsletter), max(stars), max(discord))

    def scale_x(i): return pad_l + i * chart_w / (len(months) - 1)
    def scale_y(v): return pad_t + chart_h - (v / max_val) * chart_h

    def polyline(series, color):
        pts = " ".join(f"{scale_x(i):.1f},{scale_y(v):.1f}" for i, v in enumerate(series))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'

    dots = ""
    for i, v in enumerate(newsletter):
        dots += f'<circle cx="{scale_x(i):.1f}" cy="{scale_y(v):.1f}" r="3" fill="#C74634"/>'
    for i, v in enumerate(stars):
        dots += f'<circle cx="{scale_x(i):.1f}" cy="{scale_y(v):.1f}" r="3" fill="#38bdf8"/>'
    for i, v in enumerate(discord):
        dots += f'<circle cx="{scale_x(i):.1f}" cy="{scale_y(v):.1f}" r="3" fill="#4ade80"/>'

    x_labels = "".join(
        f'<text x="{scale_x(i):.1f}" y="{pad_t + chart_h + 14}" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>'
        for i, m in enumerate(months)
    )
    # Y gridlines
    grids = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        yg = pad_t + chart_h - frac * chart_h
        val = int(frac * max_val)
        grids += f'<line x1="{pad_l}" y1="{yg:.1f}" x2="{pad_l+chart_w}" y2="{yg:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grids += f'<text x="{pad_l - 6}" y="{yg + 3:.1f}" fill="#475569" font-size="8" text-anchor="end">{val}</text>'

    legend_y = pad_t + 2
    legend = (f'<rect x="{pad_l}" y="{legend_y}" width="10" height="4" fill="#C74634" rx="1"/>'
              f'<text x="{pad_l+13}" y="{legend_y+4}" fill="#94a3b8" font-size="8">Newsletter</text>'
              f'<rect x="{pad_l+75}" y="{legend_y}" width="10" height="4" fill="#38bdf8" rx="1"/>'
              f'<text x="{pad_l+88}" y="{legend_y+4}" fill="#94a3b8" font-size="8">GitHub Stars</text>'
              f'<rect x="{pad_l+165}" y="{legend_y}" width="10" height="4" fill="#4ade80" rx="1"/>'
              f'<text x="{pad_l+178}" y="{legend_y+4}" fill="#94a3b8" font-size="8">Discord</text>')

    svg = f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>
  {grids}
  {polyline(newsletter, "#C74634")}
  {polyline(stars, "#38bdf8")}
  {polyline(discord, "#4ade80")}
  {dots}
  {x_labels}
  {legend}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>
  <line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>
</svg>'''
    return svg


def build_html():
    community_svg = build_community_svg()
    total_views = sum(c["views"] for c in CONTENT_ITEMS)
    total_leads = sum(c["leads"] for c in CONTENT_ITEMS)

    content_rows = ""
    for c in CONTENT_ITEMS:
        ctype_colors = {"GTC Talk": "#C74634", "Blog Post": "#38bdf8", "Demo Video": "#4ade80",
                        "GitHub README": "#fbbf24", "Newsletter": "#a78bfa", "CoRL Paper": "#f472b6"}
        color = ctype_colors.get(c["type"], "#94a3b8")
        content_rows += f'''
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 8px;"><span style="background:#0f172a;color:{color};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">{c["type"]}</span></td>
          <td style="padding:10px 8px;color:#94a3b8;font-size:13px;max-width:260px;">{c["title"]}</td>
          <td style="padding:10px 8px;text-align:right;color:#f1f5f9;font-weight:600;">{c["views"]:,}</td>
          <td style="padding:10px 8px;text-align:right;color:#4ade80;font-weight:700;">{c["leads"]}</td>
          <td style="padding:10px 8px;text-align:right;color:#fbbf24;font-weight:700;">{c["roi"]}</td>
        </tr>'''

    conf_status_colors = {"confirmed": "#4ade80", "submitted": "#fbbf24", "planned": "#64748b"}
    conf_rows = ""
    for conf in CONFERENCES:
        sc = conf_status_colors.get(conf["status"], "#94a3b8")
        conf_rows += f'''
        <div style="background:#1e293b;border-radius:10px;padding:14px;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="color:#f1f5f9;font-weight:700;font-size:14px;">{conf["name"]}</div>
            <div style="color:#64748b;font-size:11px;">{conf["date"]} &bull; {conf["type"]}</div>
          </div>
          <div style="text-align:right;">
            <div style="color:#38bdf8;font-weight:700;font-size:16px;">{conf["expected_leads"]} leads</div>
            <span style="color:{sc};font-size:11px;font-weight:600;">{conf["status"].upper()}</span>
          </div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SERVICE_TITLE} — Port {PORT}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom: 1px solid #334155; padding: 24px 32px; }}
  .badge {{ display: inline-block; background: #C74634; color: #fff; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-bottom: 8px; }}
  h1 {{ font-size: 28px; color: #C74634; font-weight: 800; }}
  .subtitle {{ color: #64748b; font-size: 14px; margin-top: 4px; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border-radius: 10px; padding: 18px; border-top: 3px solid #C74634; }}
  .kpi-value {{ font-size: 26px; font-weight: 800; color: #f1f5f9; }}
  .kpi-label {{ color: #64748b; font-size: 12px; margin-top: 4px; }}
  .section-title {{ color: #38bdf8; font-size: 16px; font-weight: 700; margin-bottom: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 28px; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
  .conf-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .footer {{ text-align: center; color: #334155; font-size: 11px; padding: 20px; border-top: 1px solid #1e293b; margin-top: 20px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  @media (max-width: 700px) {{ .kpi-grid {{ grid-template-columns: repeat(2,1fr); }} .grid2 {{ grid-template-columns: 1fr; }} .conf-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="header">
  <span class="badge">Port {PORT}</span>
  <h1>{SERVICE_TITLE}</h1>
  <div class="subtitle">Content marketing &bull; Community growth &bull; SEO &bull; Conference pipeline &bull; 28%/mo newsletter growth</div>
</div>
<div class="container">
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-value">{METRICS["github_stars"]:,}</div><div class="kpi-label">GitHub Stars</div></div>
    <div class="kpi"><div class="kpi-value">{METRICS["newsletter_subs"]:,}</div><div class="kpi-label">Newsletter Subscribers (+{METRICS["newsletter_growth_pct"]}%/mo)</div></div>
    <div class="kpi"><div class="kpi-value">{METRICS["gtc_talk_views"]:,}</div><div class="kpi-label">GTC Talk Views → {METRICS["gtc_leads"]} Leads</div></div>
    <div class="kpi"><div class="kpi-value">{METRICS["discord_members"]}</div><div class="kpi-label">Discord Members</div></div>
  </div>

  <div class="grid2">
    <div class="card">
      <div class="section-title">Community Growth (8 Months)</div>
      {community_svg}
      <div style="display:flex;gap:20px;margin-top:12px;">
        <div style="text-align:center;"><div style="color:#C74634;font-weight:700;">{METRICS["newsletter_subs"]:,}</div><div style="color:#64748b;font-size:11px;">Newsletter Now</div></div>
        <div style="text-align:center;"><div style="color:#38bdf8;font-weight:700;">{METRICS["github_stars"]}</div><div style="color:#64748b;font-size:11px;">GitHub Stars</div></div>
        <div style="text-align:center;"><div style="color:#4ade80;font-weight:700;">{METRICS["github_contributors"]}</div><div style="color:#64748b;font-size:11px;">Contributors</div></div>
      </div>
    </div>
    <div class="card">
      <div class="section-title">SEO Performance</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <div style="background:#0f172a;border-radius:8px;padding:14px;text-align:center;">
          <div style="color:#38bdf8;font-size:24px;font-weight:800;">{METRICS["seo_keywords"]}</div>
          <div style="color:#64748b;font-size:11px;">Keywords Ranking</div>
        </div>
        <div style="background:#0f172a;border-radius:8px;padding:14px;text-align:center;">
          <div style="color:#4ade80;font-size:24px;font-weight:800;">{METRICS["seo_rank_top10"]}</div>
          <div style="color:#64748b;font-size:11px;">Top-10 Rankings</div>
        </div>
        <div style="background:#0f172a;border-radius:8px;padding:14px;text-align:center;">
          <div style="color:#fbbf24;font-size:24px;font-weight:800;">{METRICS["blog_traffic"]:,}</div>
          <div style="color:#64748b;font-size:11px;">Monthly Blog Visits</div>
        </div>
        <div style="background:#0f172a;border-radius:8px;padding:14px;text-align:center;">
          <div style="color:#C74634;font-size:24px;font-weight:800;">{METRICS["blog_posts"]}</div>
          <div style="color:#64748b;font-size:11px;">Published Posts</div>
        </div>
      </div>
      <div style="background:#0f172a;border-radius:8px;padding:12px;">
        <div style="color:#38bdf8;font-size:11px;font-weight:700;margin-bottom:6px;">Top Keywords</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;">
          {" ".join(f'<span style="background:#1e293b;color:#94a3b8;padding:3px 8px;border-radius:10px;font-size:10px;">{kw}</span>' for kw in ["robot policy fine-tuning", "GR00T OCI", "LIBERO simulation", "LoRA robot adapter", "cloud robotics training"])}
        </div>
      </div>
    </div>
  </div>

  <div style="margin-bottom:28px;">
    <div class="section-title">Content ROI — All Channels</div>
    <div class="card" style="padding:0;">
      <table>
        <thead>
          <tr style="background:#0f172a;color:#64748b;font-size:12px;">
            <th style="text-align:left;padding:12px 16px;">Type</th>
            <th style="text-align:left;padding:12px 8px;">Title</th>
            <th style="text-align:right;padding:12px 8px;">Views</th>
            <th style="text-align:right;padding:12px 8px;">Leads</th>
            <th style="text-align:right;padding:12px 16px;">ROI</th>
          </tr>
        </thead>
        <tbody style="font-size:13px;">
          {content_rows}
        </tbody>
        <tfoot>
          <tr style="background:#0f172a;font-weight:700;">
            <td colspan="2" style="padding:10px 16px;color:#64748b;">TOTAL</td>
            <td style="text-align:right;padding:10px 8px;color:#f1f5f9;">{total_views:,}</td>
            <td style="text-align:right;padding:10px 8px;color:#4ade80;">{total_leads}</td>
            <td style="text-align:right;padding:10px 16px;color:#fbbf24;">~2,100%</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>

  <div>
    <div class="section-title">Conference Pipeline — {METRICS["conference_pipeline"]} Events</div>
    <div class="conf-grid">
      {conf_rows}
    </div>
  </div>
</div>
<div class="footer">OCI Robot Cloud &bull; {SERVICE_TITLE} &bull; Port {PORT} &bull; {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}</div>
</body>
</html>'''
    return html


if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT}

    @app.get("/metrics")
    def metrics():
        return METRICS

    @app.get("/content")
    def content():
        return {"content": CONTENT_ITEMS, "total_views": sum(c["views"] for c in CONTENT_ITEMS), "total_leads": sum(c["leads"] for c in CONTENT_ITEMS)}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *a): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        srv = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"{SERVICE_TITLE} running on port {PORT} (stdlib fallback)")
        srv.serve_forever()
