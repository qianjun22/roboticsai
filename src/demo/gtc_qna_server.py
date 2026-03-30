"""
GTC 2027 Live Q&A Demonstration Server — OCI Robot Cloud
Port 8050

Audience members scan a QR code, submit questions, upvote others.
Presenter views a live dashboard and answers in real-time.
"""

import argparse
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, Form, Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    pass

DB_PATH = "/tmp/gtc_qna.db"

EXAMPLE_QUESTIONS = [
    ("How does DAgger compare to behavior cloning in terms of sample efficiency on real robot arms?", "Alex Chen", "technical"),
    ("What GPU instance types does OCI Robot Cloud support for GR00T N1.6 inference?", "Priya Patel", "technical"),
    ("What is the cost per 10,000 training steps on OCI A100 instances?", "Marcus Lee", "business"),
    ("Is there a NVIDIA partnership or OEM agreement behind this platform?", "Sarah Kim", "business"),
    ("How does GR00T N1.6 handle out-of-distribution objects it hasn't seen in training?", "Jordan Wu", "technical"),
    ("What's the roadmap for Jetson Orin edge deployment — when is GA?", "David Nguyen", "roadmap"),
    ("Can the fine-tuning pipeline ingest data from third-party teleoperation rigs?", "Emily Tran", "technical"),
    ("What success rate benchmarks have design partners achieved on pick-and-place tasks?", "Ryan Park", "benchmark"),
    ("How does OCI Robot Cloud compare to AWS RoboMaker on latency and throughput?", "Lisa Zhao", "benchmark"),
    ("Is there a free tier or research program for universities?", "Anonymous", "business"),
    ("What sim-to-real gap mitigation techniques are built into the Isaac Sim SDG pipeline?", "Tom Okonkwo", "technical"),
    ("When will multi-arm coordination be supported for dual-arm manipulation tasks?", "Nina Patel", "roadmap"),
    ("How does the data flywheel work — does production inference data automatically feed back into training?", "Carlos Rivera", "technical"),
    ("What's the minimum dataset size recommended before starting DAgger fine-tuning?", "Yuki Tanaka", "benchmark"),
    ("Are there plans for a Cosmos world model integration for synthetic data generation at scale?", "Aisha Mohamed", "roadmap"),
]

KEYWORD_CATEGORY_MAP = {
    "technical": ["dagger", "training", "inference", "model", "gr00t", "finetune", "fine-tune",
                  "pipeline", "sim", "sdg", "isaac", "libero", "gpu", "latency", "checkpoint",
                  "dataset", "episode", "policy", "distillation", "teleoperation", "ik", "arm"],
    "business":  ["price", "cost", "pricing", "partner", "partnership", "nvidia", "oem",
                  "enterprise", "tier", "free", "revenue", "contract", "license", "university"],
    "benchmark": ["benchmark", "success rate", "performance", "compare", "comparison",
                  "throughput", "accuracy", "mae", "score", "metric", "result"],
    "roadmap":   ["roadmap", "when", "ga", "general availability", "future", "plan", "next",
                  "upcoming", "release", "q1", "q2", "q3", "q4", "2027", "2028"],
}


def detect_category(text: str) -> str:
    lower = text.lower()
    scores = {cat: 0 for cat in KEYWORD_CATEGORY_MAP}
    for cat, keywords in KEYWORD_CATEGORY_MAP.items():
        for kw in keywords:
            if kw in lower:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "technical"


@dataclass
class Question:
    q_id: int
    text: str
    asked_by: str
    asked_at: str
    upvotes: int
    answered: bool
    answer_text: Optional[str]
    category: str


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(load_examples: bool = True):
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            q_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            text       TEXT NOT NULL,
            asked_by   TEXT NOT NULL DEFAULT 'Anonymous',
            asked_at   TEXT NOT NULL,
            upvotes    INTEGER NOT NULL DEFAULT 0,
            answered   INTEGER NOT NULL DEFAULT 0,
            answer_text TEXT,
            category   TEXT NOT NULL DEFAULT 'technical'
        )
    """)
    conn.commit()

    if load_examples:
        count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            for text, name, category in EXAMPLE_QUESTIONS:
                conn.execute(
                    "INSERT INTO questions (text, asked_by, asked_at, upvotes, answered, category) VALUES (?,?,?,?,0,?)",
                    (text, name, datetime.utcnow().isoformat(), 0, category),
                )
            conn.commit()
    conn.close()


def fetch_questions(unanswered_only: bool = False) -> list[Question]:
    conn = get_db()
    sql = "SELECT * FROM questions"
    if unanswered_only:
        sql += " WHERE answered = 0"
    sql += " ORDER BY upvotes DESC, q_id ASC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [
        Question(
            q_id=r["q_id"],
            text=r["text"],
            asked_by=r["asked_by"],
            asked_at=r["asked_at"],
            upvotes=r["upvotes"],
            answered=bool(r["answered"]),
            answer_text=r["answer_text"],
            category=r["category"],
        )
        for r in rows
    ]


def add_question(text: str, asked_by: str) -> int:
    category = detect_category(text)
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO questions (text, asked_by, asked_at, upvotes, answered, category) VALUES (?,?,?,0,0,?)",
        (text, asked_by or "Anonymous", datetime.utcnow().isoformat(), category),
    )
    conn.commit()
    q_id = cur.lastrowid
    conn.close()
    return q_id


def upvote_question(q_id: int) -> int:
    conn = get_db()
    conn.execute("UPDATE questions SET upvotes = upvotes + 1 WHERE q_id = ?", (q_id,))
    conn.commit()
    new_count = conn.execute("SELECT upvotes FROM questions WHERE q_id = ?", (q_id,)).fetchone()
    conn.close()
    return new_count["upvotes"] if new_count else 0


def answer_question(q_id: int, answer_text: str):
    conn = get_db()
    conn.execute(
        "UPDATE questions SET answered = 1, answer_text = ? WHERE q_id = ?",
        (answer_text, q_id),
    )
    conn.commit()
    conn.close()


# ── HTML helpers ──────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "technical": "#3b82f6",
    "business":  "#f59e0b",
    "benchmark": "#8b5cf6",
    "roadmap":   "#10b981",
}


def badge(category: str) -> str:
    color = CATEGORY_COLORS.get(category, "#6b7280")
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;text-transform:uppercase">{category}</span>'


def audience_html(questions: list[Question]) -> str:
    unanswered_count = sum(1 for q in questions if not q.answered)
    rows = ""
    for q in questions:
        answered_badge = '<span style="color:#22c55e;font-weight:700;font-size:14px"> ✓ Answered</span>' if q.answered else ""
        answer_block = ""
        if q.answered and q.answer_text:
            answer_block = f'<div style="margin-top:8px;padding:8px 12px;background:#1a2a1a;border-left:3px solid #22c55e;color:#86efac;font-size:13px"><strong>Answer:</strong> {q.answer_text}</div>'
        rows += f"""
        <div style="background:#1e2433;border-radius:10px;padding:16px;margin-bottom:12px;border:1px solid #2d3748">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
            <div style="flex:1">
              <p style="margin:0 0 6px 0;font-size:16px;line-height:1.4">{q.text}</p>
              <div style="display:flex;align-items:center;gap:8px;font-size:12px;color:#9ca3af">
                {badge(q.category)} &nbsp;asked by <em>{q.asked_by}</em>{answered_badge}
              </div>
              {answer_block}
            </div>
            <form method="post" action="/upvote/{q.q_id}" style="flex-shrink:0;text-align:center">
              <button type="submit" style="background:#2563eb;border:none;color:#fff;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:13px">
                ▲<br><strong>{q.upvotes}</strong>
              </button>
            </form>
          </div>
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>GTC 2027 — OCI Robot Cloud Q&A</title>
<style>*{{box-sizing:border-box}}body{{background:#0f1623;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:16px}}
input,textarea{{background:#1e2433;color:#e2e8f0;border:1px solid #374151;border-radius:6px;padding:10px;width:100%;font-size:14px;margin-bottom:8px}}
button.submit{{background:#16a34a;color:#fff;border:none;border-radius:6px;padding:10px 24px;font-size:15px;cursor:pointer;width:100%}}
</style></head><body>
<div style="max-width:720px;margin:0 auto">
  <div style="text-align:center;margin-bottom:24px">
    <h1 style="font-size:26px;margin:0;color:#60a5fa">OCI Robot Cloud</h1>
    <p style="color:#9ca3af;margin:4px 0 0">GTC 2027 Live Q&amp;A &nbsp;·&nbsp; {unanswered_count} questions pending</p>
  </div>

  <div style="background:#1e2433;border-radius:12px;padding:20px;margin-bottom:28px;border:1px solid #2d3748">
    <h2 style="margin:0 0 14px;font-size:16px;color:#a5b4fc">Ask a Question</h2>
    <form method="post" action="/ask">
      <textarea name="text" rows="3" placeholder="Type your question about OCI Robot Cloud..." required></textarea>
      <input name="name" type="text" placeholder="Your name (optional)">
      <button class="submit" type="submit">Submit Question</button>
    </form>
  </div>

  <h2 style="font-size:16px;color:#a5b4fc;margin-bottom:12px">Questions — ranked by upvotes</h2>
  {rows if rows else '<p style="color:#6b7280">No questions yet. Be the first!</p>'}
</div></body></html>"""


def presenter_html(questions: list[Question]) -> str:
    unanswered = [q for q in questions if not q.answered]
    all_qs = questions

    def q_row(q: Question, show_answer_form: bool) -> str:
        answer_form = ""
        if show_answer_form:
            answer_form = f"""<form method="post" action="/answer/{q.q_id}" style="margin-top:8px;display:flex;gap:6px">
              <input name="answer_text" type="text" placeholder="Type answer..." style="flex:1;background:#12171f;color:#e2e8f0;border:1px solid #374151;border-radius:6px;padding:6px 10px;font-size:13px">
              <button type="submit" style="background:#16a34a;color:#fff;border:none;border-radius:6px;padding:6px 14px;font-size:13px;cursor:pointer">Answer</button>
            </form>"""
        answered_txt = '<span style="color:#22c55e"> ✓</span>' if q.answered else ""
        return f"""<div style="background:#12171f;border-radius:8px;padding:12px;margin-bottom:8px;border:1px solid #1f2937">
          <div style="font-size:13px;margin-bottom:4px">{badge(q.category)} &nbsp;<span style="color:#9ca3af">{q.asked_by}</span> &nbsp;▲ {q.upvotes}{answered_txt}</div>
          <p style="margin:0;font-size:14px">{q.text}</p>
          {answer_form}
        </div>"""

    top_rows = "".join(q_row(q, True) for q in unanswered[:10]) or '<p style="color:#6b7280;font-size:13px">All answered!</p>'
    all_rows = "".join(q_row(q, False) for q in all_qs) or '<p style="color:#6b7280;font-size:13px">None yet.</p>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3">
<title>Presenter View — GTC 2027 Q&A</title>
<style>*{{box-sizing:border-box}}body{{background:#0a0e17;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:16px}}
h2{{font-size:14px;color:#a5b4fc;margin:0 0 10px}}
</style></head><body>
<div style="display:flex;gap:16px;height:calc(100vh - 32px)">
  <div style="flex:1;overflow-y:auto;background:#1e2433;border-radius:12px;padding:16px;border:1px solid #2d3748">
    <h2>Top Unanswered — {len(unanswered)} remaining</h2>
    {top_rows}
  </div>
  <div style="flex:1;overflow-y:auto;background:#1e2433;border-radius:12px;padding:16px;border:1px solid #2d3748">
    <h2>All Questions ({len(all_qs)})</h2>
    {all_rows}
  </div>
</div></body></html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(title="GTC 2027 Q&A Server", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def audience_view():
        questions = fetch_questions()
        return audience_html(questions)

    @app.get("/present", response_class=HTMLResponse)
    async def presenter_view():
        questions = fetch_questions()
        return presenter_html(questions)

    @app.post("/ask")
    async def ask(text: str = Form(...), name: str = Form(default="Anonymous")):
        if text.strip():
            add_question(text.strip(), name.strip() or "Anonymous")
        return RedirectResponse(url="/", status_code=303)

    @app.post("/upvote/{q_id}")
    async def upvote(q_id: int):
        new_count = upvote_question(q_id)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/answer/{q_id}")
    async def answer(q_id: int, answer_text: str = Form(...)):
        if answer_text.strip():
            answer_question(q_id, answer_text.strip())
        return RedirectResponse(url="/present", status_code=303)

    @app.get("/api/questions")
    async def api_questions(unanswered_only: bool = False):
        questions = fetch_questions(unanswered_only=unanswered_only)
        return JSONResponse([
            {
                "q_id": q.q_id,
                "text": q.text,
                "asked_by": q.asked_by,
                "asked_at": q.asked_at,
                "upvotes": q.upvotes,
                "answered": q.answered,
                "answer_text": q.answer_text,
                "category": q.category,
            }
            for q in questions
        ])

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gtc_qna_server", "port": 8050}


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GTC 2027 Live Q&A Server — OCI Robot Cloud")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    parser.add_argument("--mock", action="store_true", help="Load 15 example questions on startup (default: True when DB empty)")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("ERROR: FastAPI and uvicorn are required. Install with:")
        print("  pip install fastapi uvicorn")
        return

    init_db(load_examples=True)
    print(f"GTC 2027 Q&A Server starting on http://{args.host}:{args.port}")
    print(f"  Audience view:   http://localhost:{args.port}/")
    print(f"  Presenter view:  http://localhost:{args.port}/present")
    print(f"  API:             http://localhost:{args.port}/api/questions")
    print(f"  DB:              {DB_PATH}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
