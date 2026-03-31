"""Content marketing execution calendar
FastAPI service — OCI Robot Cloud
Port: 10149"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10149

# Monthly themes
MONTHLY_THEMES = {
    1:  "sim-to-real",
    2:  "DAgger explained",
    3:  "case study",
    4:  "AI World preview",
    5:  "Series A",
    6:  "sim-to-real",
    7:  "DAgger explained",
    8:  "case study",
    9:  "AI World preview",
    10: "Series A",
    11: "sim-to-real",
    12: "year-in-review",
}

# Content performance by type
CONTENT_PERFORMANCE = {
    "blog": {
        "views": 2300,
        "views_label": "2.3K/mo",
        "engagement_rate": 0.047,
        "pipeline_attribution": 0.31,
        "pipeline_label": "31% pipeline attribution",
        "avg_read_time_min": 4.2,
    },
    "github": {
        "stars": 847,
        "forks": 213,
        "engagement_rate": 0.082,
        "pipeline_attribution": 0.18,
        "pipeline_label": "18% pipeline attribution",
        "weekly_growth": 12,
    },
    "linkedin": {
        "impressions": 14200,
        "clicks": 831,
        "engagement_rate": 0.059,
        "pipeline_attribution": 0.22,
        "pipeline_label": "22% pipeline attribution",
    },
    "webinar": {
        "registrants": 340,
        "attendees": 198,
        "attendance_rate": 0.582,
        "pipeline_attribution": 0.41,
        "pipeline_label": "41% pipeline attribution (highest)",
    },
    "demo_video": {
        "views": 5600,
        "completion_rate": 0.63,
        "pipeline_attribution": 0.28,
        "pipeline_label": "28% pipeline attribution",
    },
}

# 8-week AI World countdown schedule (weeks before event)
AI_WORLD_COUNTDOWN = [
    {"weeks_before": 8, "action": "Announce session abstract + speaker lineup", "channel": "blog+linkedin"},
    {"weeks_before": 7, "action": "Release GR00T fine-tuning benchmark blog post", "channel": "blog"},
    {"weeks_before": 6, "action": "GitHub star push — open-source SDG scripts", "channel": "github"},
    {"weeks_before": 5, "action": "Customer case study: lift task 85% SR", "channel": "blog+linkedin"},
    {"weeks_before": 4, "action": "Live webinar: OCI Robot Cloud deep-dive", "channel": "webinar"},
    {"weeks_before": 3, "action": "Demo video release: closed-loop eval on A100", "channel": "demo_video"},
    {"weeks_before": 2, "action": "Series A announcement teaser", "channel": "linkedin"},
    {"weeks_before": 1, "action": "Final push: booth details + meeting scheduler", "channel": "linkedin+email"},
]

def _generate_monthly_calendar(month: int):
    theme = MONTHLY_THEMES.get(month, "sim-to-real")
    random.seed(month * 42)
    content_types = ["blog", "linkedin", "github", "webinar", "demo_video"]
    scheduled = []
    # Roughly 8-12 pieces per month
    n_pieces = random.randint(8, 12)
    for i in range(n_pieces):
        day = random.randint(1, 28)
        ctype = random.choice(content_types)
        reach = {
            "blog": random.randint(1800, 3200),
            "linkedin": random.randint(8000, 18000),
            "github": random.randint(200, 600),
            "webinar": random.randint(150, 400),
            "demo_video": random.randint(3000, 8000),
        }[ctype]
        scheduled.append({
            "day": day,
            "type": ctype,
            "theme": theme,
            "title": f"{theme.title()} — {ctype.replace('_',' ').title()} #{i+1}",
            "status": random.choice(["scheduled", "scheduled", "draft", "published"]),
            "expected_reach": reach,
        })
    scheduled.sort(key=lambda x: x["day"])
    return scheduled

if USE_FASTAPI:
    app = FastAPI(title="Content Marketing Calendar", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(
            f"<html><head><title>Content Marketing Calendar</title>"
            f"<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}"
            f"h1{{color:#C74634}}a{{color:#38bdf8}}</style></head>"
            f"<body><h1>Content Marketing Calendar</h1>"
            f"<p>OCI Robot Cloud · Port {PORT}</p>"
            f"<p>2.3K blog views/mo · 847 GitHub stars · 31% pipeline attribution</p>"
            f"<p><a href='/docs'>API Docs</a></p></body></html>"
        )

    @app.get("/content/calendar")
    def get_calendar(month: int = None):
        """
        Return scheduled content for a given month (1-12).
        Defaults to current month if not specified.
        """
        if month is None:
            month = datetime.utcnow().month
        if month < 1 or month > 12:
            return JSONResponse({"error": "month must be 1-12"}, status_code=422)

        scheduled = _generate_monthly_calendar(month)
        theme = MONTHLY_THEMES.get(month, "sim-to-real")
        total_reach = sum(c["expected_reach"] for c in scheduled)
        return {
            "month": month,
            "theme": theme,
            "scheduled_content": scheduled,
            "total_pieces": len(scheduled),
            "total_expected_reach": total_reach,
            "ai_world_countdown": AI_WORLD_COUNTDOWN,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/content/performance")
    def get_performance(content_type: str = None):
        """
        Return performance metrics by content type.
        Query param: content_type (blog/github/linkedin/webinar/demo_video)
        Returns all types if omitted.
        """
        if content_type:
            if content_type not in CONTENT_PERFORMANCE:
                return JSONResponse(
                    {"error": f"Unknown type '{content_type}'. Valid: {list(CONTENT_PERFORMANCE.keys())}"},
                    status_code=404
                )
            return {
                "content_type": content_type,
                **CONTENT_PERFORMANCE[content_type],
                "ts": datetime.utcnow().isoformat(),
            }
        # Aggregate
        avg_pipeline = round(
            sum(v["pipeline_attribution"] for v in CONTENT_PERFORMANCE.values()) /
            len(CONTENT_PERFORMANCE), 3
        )
        return {
            "performance_by_type": CONTENT_PERFORMANCE,
            "avg_pipeline_attribution": avg_pipeline,
            "blog_views_per_month": 2300,
            "github_stars": 847,
            "top_channel_by_pipeline": "webinar",
            "ts": datetime.utcnow().isoformat(),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a):
            pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
