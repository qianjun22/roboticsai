"""
Customer feedback analyzer — NPS tracking, qualitative theme extraction, feedback-to-roadmap routing, sentiment analysis.
FastAPI service — OCI Robot Cloud
Port: 10079
"""
from __future__ import annotations
import json, math, random, time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10079

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

_THEMES = [
    "inference_latency",
    "sdk_usability",
    "fine_tuning_pipeline",
    "sim_to_real_gap",
    "documentation",
    "pricing",
    "multi_robot_support",
    "safety_guarantees",
    "onboarding",
    "support_responsiveness",
]

_ROADMAP_OWNERS = {
    "inference_latency": "platform-eng",
    "sdk_usability": "dx-team",
    "fine_tuning_pipeline": "ml-infra",
    "sim_to_real_gap": "research",
    "documentation": "dx-team",
    "pricing": "product-gtm",
    "multi_robot_support": "platform-eng",
    "safety_guarantees": "research",
    "onboarding": "dx-team",
    "support_responsiveness": "customer-success",
}

_SENTIMENT_KEYWORDS = {
    "positive": ["great", "love", "excellent", "fast", "easy", "smooth", "awesome", "helpful", "reliable", "good"],
    "negative": ["slow", "broken", "crash", "difficult", "confusing", "expensive", "bug", "fail", "poor", "missing"],
    "neutral": ["okay", "fine", "average", "normal", "expected", "standard"],
}

# ---------------------------------------------------------------------------
# In-memory feedback store
# ---------------------------------------------------------------------------

_FEEDBACK_STORE: List[Dict[str, Any]] = []

# Seed with synthetic historical data so the analysis endpoint returns meaningful results
def _seed_historical():
    rng = random.Random(42)
    base_ts = datetime.now(timezone.utc) - timedelta(days=90)
    customers = [f"cust_{i:03d}" for i in range(1, 31)]
    types = ["nps", "qualitative", "bug_report", "feature_request"]
    for i in range(120):
        days_offset = rng.uniform(0, 89)
        ts = base_ts + timedelta(days=days_offset)
        fb_type = rng.choice(types)
        theme = rng.choice(_THEMES)
        sentiment_key = rng.choices(["positive", "negative", "neutral"], weights=[0.45, 0.35, 0.20])[0]
        sample_word = rng.choice(_SENTIMENT_KEYWORDS[sentiment_key])
        nps_score = None
        if fb_type == "nps":
            if sentiment_key == "positive":
                nps_score = rng.randint(8, 10)
            elif sentiment_key == "negative":
                nps_score = rng.randint(0, 6)
            else:
                nps_score = rng.randint(6, 8)
        _FEEDBACK_STORE.append({
            "id": f"fb_{i:04d}",
            "customer_id": rng.choice(customers),
            "type": fb_type,
            "content": f"The {theme.replace('_', ' ')} is {sample_word}. Please consider improving it.",
            "nps_score": nps_score,
            "theme": theme,
            "sentiment": sentiment_key,
            "routed_to": _ROADMAP_OWNERS[theme],
            "product_action": f"Review {theme.replace('_', ' ')} based on {sentiment_key} feedback",
            "ts": ts.isoformat(),
        })

_seed_historical()

# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _parse_timerange(timerange: str) -> Optional[datetime]:
    """Convert a timerange string like '7d', '30d', '90d' to a cutoff datetime."""
    _map = {"7d": 7, "30d": 30, "90d": 90, "all": 36500}
    days = _map.get(timerange)
    if days is None:
        try:
            days = int(timerange.rstrip("d"))
        except ValueError:
            return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _compute_nps(scores: List[int]) -> float:
    """Compute NPS from a list of 0-10 scores."""
    if not scores:
        return 0.0
    promoters = sum(1 for s in scores if s >= 9)
    detractors = sum(1 for s in scores if s <= 6)
    n = len(scores)
    return round(100 * (promoters - detractors) / n, 1)


def _extract_themes(entries: List[Dict]) -> List[Dict[str, Any]]:
    """Aggregate theme frequency and sentiment breakdown."""
    theme_data: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "positive": 0, "negative": 0, "neutral": 0})
    for e in entries:
        t = e.get("theme", "unknown")
        theme_data[t]["count"] += 1
        sentiment = e.get("sentiment", "neutral")
        theme_data[t][sentiment] = theme_data[t].get(sentiment, 0) + 1
    result = []
    for theme, data in sorted(theme_data.items(), key=lambda x: -x[1]["count"]):
        result.append({
            "theme": theme,
            "count": data["count"],
            "sentiment_breakdown": {
                "positive": data.get("positive", 0),
                "negative": data.get("negative", 0),
                "neutral": data.get("neutral", 0),
            },
            "owner": _ROADMAP_OWNERS.get(theme, "tbd"),
        })
    return result


def _analyze_sentiment(entries: List[Dict]) -> Dict[str, Any]:
    counts = defaultdict(int)
    for e in entries:
        counts[e.get("sentiment", "neutral")] += 1
    total = max(len(entries), 1)
    return {
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
        "positive_pct": round(100 * counts["positive"] / total, 1),
        "negative_pct": round(100 * counts["negative"] / total, 1),
    }


def _generate_product_actions(entries: List[Dict]) -> List[str]:
    """Derive top product actions from the most-mentioned negative themes."""
    neg_themes: Dict[str, int] = defaultdict(int)
    for e in entries:
        if e.get("sentiment") == "negative":
            neg_themes[e.get("theme", "unknown")] += 1
    top = sorted(neg_themes.items(), key=lambda x: -x[1])[:5]
    actions = []
    for theme, count in top:
        owner = _ROADMAP_OWNERS.get(theme, "tbd")
        actions.append(f"[{owner}] Address '{theme.replace('_', ' ')}' — {count} negative mentions")
    return actions


def _infer_sentiment(content: str) -> str:
    """Simple keyword-based sentiment inference."""
    words = set(content.lower().split())
    pos = sum(1 for w in _SENTIMENT_KEYWORDS["positive"] if w in words)
    neg = sum(1 for w in _SENTIMENT_KEYWORDS["negative"] if w in words)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _infer_theme(content: str) -> str:
    """Infer theme from content keywords."""
    content_lower = content.lower()
    for theme in _THEMES:
        if any(part in content_lower for part in theme.split("_")):
            return theme
    return random.choice(_THEMES)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Customer Feedback Analyzer",
        version="1.0.0",
        description="NPS tracking, qualitative theme extraction, feedback-to-roadmap routing, and sentiment analysis.",
    )

    # --- Schemas ---

    class SubmitRequest(BaseModel):
        customer_id: str
        type: str = Field(..., description="nps | qualitative | bug_report | feature_request")
        content: str
        nps_score: Optional[int] = Field(None, ge=0, le=10)

    # --- Endpoints ---

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "customer_feedback_analyzer",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/feedback/analysis")
    def analysis(timerange: str = Query("30d", description="Time window: 7d, 30d, 90d, or all")):
        """Return NPS, themes, sentiment breakdown, and product actions for the given time window."""
        cutoff = _parse_timerange(timerange)
        if cutoff is None:
            raise HTTPException(status_code=422, detail=f"Invalid timerange: {timerange}. Use 7d, 30d, 90d, or all.")

        # Filter entries within the time window
        entries = [
            e for e in _FEEDBACK_STORE
            if datetime.fromisoformat(e["ts"]) >= cutoff
        ]

        nps_scores = [e["nps_score"] for e in entries if e.get("nps_score") is not None]
        nps = _compute_nps(nps_scores)
        themes = _extract_themes(entries)
        sentiment = _analyze_sentiment(entries)
        product_actions = _generate_product_actions(entries)

        return {
            "timerange": timerange,
            "total_responses": len(entries),
            "nps": {
                "score": nps,
                "responses": len(nps_scores),
                "promoters": sum(1 for s in nps_scores if s >= 9),
                "passives": sum(1 for s in nps_scores if 7 <= s <= 8),
                "detractors": sum(1 for s in nps_scores if s <= 6),
            },
            "themes": themes,
            "sentiment": sentiment,
            "product_actions": product_actions,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.post("/feedback/submit")
    def submit(req: SubmitRequest):
        """Submit a new piece of customer feedback; returns analyzed result and routing decision."""
        if not req.content.strip():
            raise HTTPException(status_code=422, detail="content must not be empty")
        if req.type not in ("nps", "qualitative", "bug_report", "feature_request"):
            raise HTTPException(
                status_code=422,
                detail="type must be one of: nps, qualitative, bug_report, feature_request",
            )
        if req.type == "nps" and req.nps_score is None:
            raise HTTPException(status_code=422, detail="nps_score is required for type=nps")

        sentiment = _infer_sentiment(req.content)
        theme = _infer_theme(req.content)
        owner = _ROADMAP_OWNERS.get(theme, "tbd")
        fb_id = f"fb_{len(_FEEDBACK_STORE):04d}"

        entry: Dict[str, Any] = {
            "id": fb_id,
            "customer_id": req.customer_id,
            "type": req.type,
            "content": req.content,
            "nps_score": req.nps_score,
            "theme": theme,
            "sentiment": sentiment,
            "routed_to": owner,
            "product_action": f"Review {theme.replace('_', ' ')} based on {sentiment} feedback",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        _FEEDBACK_STORE.append(entry)

        return {
            "feedback_id": fb_id,
            "analyzed_feedback": {
                "theme": theme,
                "sentiment": sentiment,
                "nps_score": req.nps_score,
                "product_action": entry["product_action"],
            },
            "routed_to": owner,
            "ts": entry["ts"],
        }

    @app.get("/feedback/summary")
    def summary():
        """Quick summary of all-time feedback counts by type and sentiment."""
        by_type: Dict[str, int] = defaultdict(int)
        by_sentiment: Dict[str, int] = defaultdict(int)
        for e in _FEEDBACK_STORE:
            by_type[e["type"]] += 1
            by_sentiment[e["sentiment"]] += 1
        return {
            "total": len(_FEEDBACK_STORE),
            "by_type": dict(by_type),
            "by_sentiment": dict(by_sentiment),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Customer Feedback Analyzer</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>Customer Feedback Analyzer</h1><p>OCI Robot Cloud · Port 10079</p>
<div class="stat"><b>Status</b><br>Online</div>
<div class="stat"><b>Mode</b><br>NPS + Theme + Sentiment</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="72" fill="#94a3b8" font-size="9" text-anchor="middle">NPS / theme / sentiment</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/feedback/analysis">Analysis (30d)</a> | <a href="/feedback/summary">Summary</a></p>
</body></html>""")

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def do_POST(self):
            self.do_GET()
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
