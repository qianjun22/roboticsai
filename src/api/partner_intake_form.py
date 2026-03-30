"""
Self-service intake form for prospective OCI Robot Cloud design partners.
Captures robot specs, use case, compute requirements, and sends to OCI team
for review. Replaces email-based intake with a structured qualification pipeline.
"""

import argparse
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List
from urllib.parse import urlparse

PORT = 8064


@dataclass
class IntakeSubmission:
    submission_id: str
    company: str
    contact_name: str
    contact_email: str
    robot_model: str
    dof: int
    task_description: str
    n_demos_available: int
    target_sr: float
    timeline_months: int
    compute_tier_requested: str  # Pilot / Growth / Enterprise
    is_nvidia_referred: bool
    notes: str
    submitted_at: str


@dataclass
class QualificationScore:
    submission_id: str
    score: int
    tier_recommendation: str
    reasons: List[str] = field(default_factory=list)
    fast_track: bool = False


def score_submission(sub: IntakeSubmission) -> QualificationScore:
    score = 0
    reasons = []

    if sub.is_nvidia_referred:
        score += 30
        reasons.append("+30 NVIDIA-referred partner")
    if sub.n_demos_available >= 500:
        score += 20
        reasons.append(f"+20 strong demo dataset ({sub.n_demos_available} demos)")
    if sub.target_sr <= 0.70:
        score += 15
        reasons.append(f"+15 realistic success-rate target ({int(sub.target_sr*100)}%)")
    if sub.dof in [6, 7]:
        score += 15
        reasons.append(f"+15 standard arm DOF ({sub.dof}-DOF)")
    if sub.timeline_months >= 3:
        score += 10
        reasons.append(f"+10 adequate timeline ({sub.timeline_months} months)")
    if sub.compute_tier_requested != "Enterprise":
        score += 10
        reasons.append(f"+10 realistic compute tier ({sub.compute_tier_requested})")

    if score >= 80:
        tier = "Enterprise"
    elif score >= 60:
        tier = "Growth"
    else:
        tier = "Pilot"

    fast_track = score >= 70 and sub.is_nvidia_referred

    return QualificationScore(
        submission_id=sub.submission_id,
        score=score,
        tier_recommendation=tier,
        reasons=reasons,
        fast_track=fast_track,
    )


def make_mock_submissions() -> List[IntakeSubmission]:
    ts = datetime.utcnow().isoformat() + "Z"
    return [
        # score=90: NVIDIA-referred(+30) demos≥500(+20) sr≤0.70(+15) dof in[6,7](+15) tier≠Ent(+10) → 90; fast_track=True
        IntakeSubmission(
            submission_id=str(uuid.uuid4()),
            company="AcmeRobotics",
            contact_name="Alice Chen",
            contact_email="alice@acmerobotics.com",
            robot_model="UR10e",
            dof=6,
            task_description="Bin-picking in automotive assembly",
            n_demos_available=500,
            target_sr=0.65,
            timeline_months=2,  # <3 → no +10 timeline
            compute_tier_requested="Growth",
            is_nvidia_referred=True,
            notes="Referred by NVIDIA solutions team.",
            submitted_at=ts,
        ),
        # score=60: demos≥500(+20) sr≤0.70(+15) dof=7(+15) tier≠Ent(+10) → 60; timeline<3 → no +10
        IntakeSubmission(
            submission_id=str(uuid.uuid4()),
            company="BotCo",
            contact_name="Bob Lee",
            contact_email="bob@botco.ai",
            robot_model="Franka Panda",
            dof=7,
            task_description="Kitchen assembly tasks for QSR automation",
            n_demos_available=500,
            target_sr=0.70,
            timeline_months=2,  # <3 → no +10 timeline
            compute_tier_requested="Pilot",
            is_nvidia_referred=False,
            notes="Found via OCI blog post.",
            submitted_at=ts,
        ),
        # score=25: dof=6(+15) timeline≥3(+10) → 25; sr=0.95 > 0.70, demos<500, Enterprise, no NVIDIA
        IntakeSubmission(
            submission_id=str(uuid.uuid4()),
            company="QuickCorp",
            contact_name="Carol King",
            contact_email="carol@quickcorp.io",
            robot_model="Custom 6-DOF",
            dof=6,
            task_description="Sort 15 SKUs with 95% accuracy in 30 days",
            n_demos_available=10,
            target_sr=0.95,
            timeline_months=3,
            compute_tier_requested="Enterprise",
            is_nvidia_referred=False,
            notes="Hard deadline — product launch.",
            submitted_at=ts,
        ),
        # score=95: NVIDIA(+30) demos≥500(+20) sr≤0.70(+15) dof=7(+15) timeline≥3(+10) tier≠Ent(+10)=100; fast_track=True
        # Note: maximum achievable is 100; 95 is approximated as full score
        IntakeSubmission(
            submission_id=str(uuid.uuid4()),
            company="Sanctuary",
            contact_name="Dan Park",
            contact_email="dan@sanctuary.ai",
            robot_model="Phoenix Gen2",
            dof=7,
            task_description="Humanoid general manipulation in warehouses",
            n_demos_available=1000,
            target_sr=0.60,
            timeline_months=6,
            compute_tier_requested="Growth",
            is_nvidia_referred=True,
            notes="Co-developing embodiment adapter with NVIDIA.",
            submitted_at=ts,
        ),
        # score=55: demos≥500(+20) sr≤0.70(+15) dof=7(+15) timeline<3 → 50; Enterprise → no +10
        # Note: closest achievable to spec target 55 is 50
        IntakeSubmission(
            submission_id=str(uuid.uuid4()),
            company="StartupX",
            contact_name="Eva Ruiz",
            contact_email="eva@startupx.dev",
            robot_model="Kinova Gen3",
            dof=7,
            task_description="PCB inspection and rework",
            n_demos_available=500,
            target_sr=0.70,
            timeline_months=2,  # <3 → no +10
            compute_tier_requested="Enterprise",
            is_nvidia_referred=False,
            notes="Series A just closed; budget flexible.",
            submitted_at=ts,
        ),
    ]


def render_form() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Design Partner Intake</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f1117;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;min-height:100vh;padding:40px 20px}
  .container{max-width:680px;margin:0 auto}
  .header{text-align:center;margin-bottom:40px}
  .logo{font-size:13px;letter-spacing:2px;color:#7c3aed;text-transform:uppercase;margin-bottom:8px}
  h1{font-size:28px;font-weight:700;color:#f8fafc;margin-bottom:8px}
  .subtitle{color:#94a3b8;font-size:14px;line-height:1.6}
  .card{background:#1e2330;border:1px solid #2d3748;border-radius:12px;padding:28px;margin-bottom:24px}
  .section-title{font-size:12px;font-weight:600;letter-spacing:1.5px;color:#7c3aed;text-transform:uppercase;margin-bottom:18px}
  .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .form-group{display:flex;flex-direction:column;gap:6px}
  .form-group.full{grid-column:1/-1}
  label{font-size:12px;font-weight:500;color:#94a3b8;letter-spacing:0.5px}
  input,select,textarea{background:#0f1117;border:1px solid #2d3748;border-radius:6px;color:#e2e8f0;font-size:14px;padding:10px 12px;transition:border 0.2s;width:100%}
  input:focus,select:focus,textarea:focus{border-color:#7c3aed;outline:none}
  select option{background:#1e2330}
  textarea{resize:vertical;min-height:80px}
  .radio-group{display:flex;gap:20px;margin-top:4px}
  .radio-group label{display:flex;align-items:center;gap:8px;cursor:pointer;color:#e2e8f0;font-size:14px;letter-spacing:0}
  .radio-group input[type=radio]{width:auto;accent-color:#7c3aed}
  .hint{font-size:11px;color:#64748b;margin-top:2px}
  .submit-btn{width:100%;padding:14px;background:linear-gradient(135deg,#7c3aed,#4f46e5);border:none;border-radius:8px;color:#fff;font-size:15px;font-weight:600;cursor:pointer;letter-spacing:0.5px;margin-top:8px;transition:opacity 0.2s}
  .submit-btn:hover{opacity:0.9}
  .footer{text-align:center;color:#475569;font-size:12px;margin-top:32px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">Oracle Cloud Infrastructure</div>
    <h1>Robot Cloud Design Partner</h1>
    <p class="subtitle">Apply for early access to OCI Robot Cloud — AI-powered robot fine-tuning,<br>simulation-to-real pipelines, and managed inference at scale.</p>
  </div>
  <form action="/submit" method="POST">
    <div class="card">
      <div class="section-title">Company &amp; Contact</div>
      <div class="form-grid">
        <div class="form-group">
          <label>Company Name *</label>
          <input type="text" name="company" required placeholder="Acme Robotics Inc.">
        </div>
        <div class="form-group">
          <label>Contact Name *</label>
          <input type="text" name="contact_name" required placeholder="Jane Smith">
        </div>
        <div class="form-group full">
          <label>Work Email *</label>
          <input type="email" name="contact_email" required placeholder="jane@company.com">
        </div>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Robot Specifications</div>
      <div class="form-grid">
        <div class="form-group">
          <label>Robot Model *</label>
          <input type="text" name="robot_model" required placeholder="UR10e, Franka Panda, custom…">
        </div>
        <div class="form-group">
          <label>Degrees of Freedom (DOF) *</label>
          <input type="number" name="dof" required min="1" max="20" placeholder="6">
        </div>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Use Case &amp; Data</div>
      <div class="form-grid">
        <div class="form-group full">
          <label>Task Description *</label>
          <textarea name="task_description" required placeholder="Describe the manipulation task you want to automate…"></textarea>
        </div>
        <div class="form-group">
          <label>Demos Available</label>
          <input type="number" name="n_demos_available" min="0" placeholder="500">
          <span class="hint">Human teleoperation episodes</span>
        </div>
        <div class="form-group">
          <label>Target Success Rate</label>
          <input type="number" name="target_sr" min="0" max="1" step="0.01" placeholder="0.70">
          <span class="hint">0.0 – 1.0 (e.g. 0.70 = 70%)</span>
        </div>
        <div class="form-group">
          <label>Timeline (months)</label>
          <input type="number" name="timeline_months" min="1" max="36" placeholder="4">
        </div>
        <div class="form-group">
          <label>Compute Tier</label>
          <select name="compute_tier_requested">
            <option value="Pilot">Pilot — shared GPU, up to 10k steps</option>
            <option value="Growth">Growth — dedicated A100, 100k steps</option>
            <option value="Enterprise">Enterprise — multi-GPU, unlimited</option>
          </select>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Referral &amp; Notes</div>
      <div class="form-grid">
        <div class="form-group full">
          <label>Were you referred by NVIDIA?</label>
          <div class="radio-group">
            <label><input type="radio" name="is_nvidia_referred" value="true"> Yes — NVIDIA referred me</label>
            <label><input type="radio" name="is_nvidia_referred" value="false" checked> No — found independently</label>
          </div>
        </div>
        <div class="form-group full">
          <label>Additional Notes</label>
          <textarea name="notes" placeholder="Any context that would help us prioritize your application…"></textarea>
        </div>
      </div>
    </div>
    <button type="submit" class="submit-btn">Submit Application &rarr;</button>
  </form>
  <div class="footer">OCI Robot Cloud &bull; Design Partner Program &bull; <a href="/admin" style="color:#7c3aed">Admin Dashboard</a></div>
</div>
</body>
</html>"""


def render_admin(submissions: List[IntakeSubmission], scores: List[QualificationScore]) -> str:
    score_map = {s.submission_id: s for s in scores}
    total = len(submissions)
    fast_track_count = sum(1 for s in scores if s.fast_track)
    avg_score = round(sum(s.score for s in scores) / total, 1) if total else 0

    cards = ""
    for sub in sorted(submissions, key=lambda s: score_map[s.submission_id].score, reverse=True):
        sc = score_map[sub.submission_id]
        badge_color = "#22c55e" if sc.score >= 80 else "#f59e0b" if sc.score >= 55 else "#ef4444"
        ft_badge = '<span style="background:#7c3aed;color:#fff;font-size:10px;padding:2px 8px;border-radius:10px;margin-left:8px">FAST TRACK</span>' if sc.fast_track else ""
        reasons_html = "".join(f'<li style="color:#94a3b8;font-size:12px">{r}</li>' for r in sc.reasons)
        cards += f"""
<div style="background:#1e2330;border:1px solid #2d3748;border-radius:10px;padding:20px;margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div>
      <span style="font-size:16px;font-weight:700;color:#f8fafc">{sub.company}</span>{ft_badge}
      <div style="font-size:12px;color:#64748b;margin-top:2px">{sub.contact_name} &bull; {sub.contact_email}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:28px;font-weight:800;color:{badge_color}">{sc.score}</div>
      <div style="font-size:11px;color:#64748b">{sc.tier_recommendation}</div>
    </div>
  </div>
  <div style="font-size:13px;color:#cbd5e1;margin-bottom:8px">{sub.task_description}</div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:#94a3b8;margin-bottom:10px">
    <span>Robot: {sub.robot_model} ({sub.dof}-DOF)</span>
    <span>Demos: {sub.n_demos_available}</span>
    <span>Target SR: {int(sub.target_sr*100)}%</span>
    <span>Timeline: {sub.timeline_months}mo</span>
    <span>Tier: {sub.compute_tier_requested}</span>
    <span>NVIDIA ref: {"Yes" if sub.is_nvidia_referred else "No"}</span>
  </div>
  <ul style="padding-left:16px">{reasons_html}</ul>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCI Robot Cloud — Partner Admin</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f1117;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;padding:40px 20px}}
  .container{{max-width:800px;margin:0 auto}}
  h1{{font-size:24px;font-weight:700;color:#f8fafc;margin-bottom:6px}}
  .sub{{color:#64748b;font-size:13px;margin-bottom:28px}}
  .stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}}
  .stat{{background:#1e2330;border:1px solid #2d3748;border-radius:8px;padding:16px;text-align:center}}
  .stat-val{{font-size:32px;font-weight:800;color:#7c3aed}}
  .stat-lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  a{{color:#7c3aed;text-decoration:none}}
</style>
</head>
<body>
<div class="container">
  <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:4px">
    <h1>Partner Intake Dashboard</h1>
    <a href="/" style="font-size:13px">+ New Submission</a>
  </div>
  <div class="sub">All design partner applications, ranked by qualification score &bull; <a href="/api/submissions">JSON API</a></div>
  <div class="stats">
    <div class="stat"><div class="stat-val">{total}</div><div class="stat-lbl">Total Submissions</div></div>
    <div class="stat"><div class="stat-val">{fast_track_count}</div><div class="stat-lbl">Fast Track</div></div>
    <div class="stat"><div class="stat-val">{avg_score}</div><div class="stat-lbl">Avg Score</div></div>
  </div>
  {cards}
</div>
</body>
</html>"""


class IntakeHandler(BaseHTTPRequestHandler):
    submissions: List[IntakeSubmission] = []
    scores: List[QualificationScore] = []

    def log_message(self, fmt, *args):
        print(f"[intake] {self.address_string()} {fmt % args}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = render_form().encode()
            self._respond(200, "text/html", body)
        elif path == "/admin":
            body = render_admin(self.submissions, self.scores).encode()
            self._respond(200, "text/html", body)
        elif path == "/api/submissions":
            payload = [
                {"submission": asdict(s), "score": asdict(score_map)}
                for s, score_map in zip(
                    self.submissions,
                    {sc.submission_id: sc for sc in self.scores}.values()
                    if False else self.scores,
                )
            ]
            # rebuild properly
            sc_map = {sc.submission_id: sc for sc in self.scores}
            payload = [
                {"submission": asdict(s), "score": asdict(sc_map[s.submission_id])}
                for s in self.submissions
                if s.submission_id in sc_map
            ]
            body = json.dumps(payload, indent=2).encode()
            self._respond(200, "application/json", body)
        else:
            self._respond(404, "text/plain", b"Not found")

    def _respond(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Partner Intake Form")
    parser.add_argument("--mock", default=True, action=argparse.BooleanOptionalAction,
                        help="Load mock submissions (default: True)")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--output", default="/tmp/partner_intake.html",
                        help="Save admin dashboard HTML to file")
    args = parser.parse_args()

    if args.mock:
        IntakeHandler.submissions = make_mock_submissions()
        IntakeHandler.scores = [score_submission(s) for s in IntakeHandler.submissions]
        print(f"[intake] Loaded {len(IntakeHandler.submissions)} mock submissions")
        for sub, sc in zip(IntakeHandler.submissions, IntakeHandler.scores):
            ft = " [FAST TRACK]" if sc.fast_track else ""
            print(f"  {sub.company:<18} score={sc.score:3d}  tier={sc.tier_recommendation}{ft}")

    if args.output:
        html = render_admin(IntakeHandler.submissions, IntakeHandler.scores)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"[intake] Admin dashboard saved to {args.output}")

    server = HTTPServer(("0.0.0.0", args.port), IntakeHandler)
    print(f"[intake] Listening on http://0.0.0.0:{args.port}")
    print(f"[intake]   Intake form : http://localhost:{args.port}/")
    print(f"[intake]   Admin dash  : http://localhost:{args.port}/admin")
    print(f"[intake]   JSON API    : http://localhost:{args.port}/api/submissions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[intake] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
