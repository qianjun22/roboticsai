#!/usr/bin/env python3
"""
gtc_registration_portal.py — GTC 2027 demo registration and attendee management portal.

Port 8063. Manages demo slot bookings for OCI Robot Cloud's GTC 2027 booth/talk,
tracks registrant profiles (company/role/interest), and sends confirmation emails.
Pre-loads with 30 mock registrants from NVIDIA ecosystem companies.

Usage:
    python src/api/gtc_registration_portal.py --mock --port 8063
    python src/api/gtc_registration_portal.py --output /tmp/gtc_registration.html
"""

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


# ── Data model ────────────────────────────────────────────────name────────────

@dataclass
class DemoSlot:
    slot_id: str
    date: str           # 2027-03-18 to 2027-03-21
    time_str: str       # "10:30 AM"
    duration_min: int   # 15 or 30
    slot_type: str      # booth / talk / private
    available: bool
    registrant_id: str


@dataclass
class Registrant:
    reg_id: str
    name: str
    company: str
    title: str
    interest: str       # robot-startup / enterprise / nvidia-team / investor / researcher
    slot_id: str
    registered_at: str
    confirmed: bool
    notes: str


# ── Mock data ─────────────────────────────────────────────────────────────────

COMPANIES = [
    ("Agility Robotics",  "Director of AI",          "robot-startup"),
    ("Boston Dynamics",   "VP Engineering",          "enterprise"),
    ("Covariant",         "CEO",                     "robot-startup"),
    ("Figure AI",         "Head of Robotics ML",     "robot-startup"),
    ("Sanctuary AI",      "CTO",                     "robot-startup"),
    ("1X Technologies",   "AI Research Lead",        "robot-startup"),
    ("Apptronik",         "VP Product",              "robot-startup"),
    ("Digit",             "Director of Perception",  "robot-startup"),
    ("NVIDIA",            "Isaac Sim Tech Lead",     "nvidia-team"),
    ("NVIDIA",            "GR00T Research Scientist","nvidia-team"),
    ("NVIDIA",            "Robotics Partner Manager","nvidia-team"),
    ("Amazon Robotics",   "Principal Scientist",     "enterprise"),
    ("Foxconn",           "AI Automation Lead",      "enterprise"),
    ("BMW Group",         "Head of Smart Factory",   "enterprise"),
    ("Siemens",           "Digital Industries PM",   "enterprise"),
    ("Softbank Robotics", "CTO Americas",            "enterprise"),
    ("FANUC America",     "Advanced AI Manager",     "enterprise"),
    ("ABB Robotics",      "VP Digital",              "enterprise"),
    ("Sequoia Capital",   "Partner",                 "investor"),
    ("Andreessen Horowitz","Principal",              "investor"),
    ("GV (Google Ventures)","Investment Director",   "investor"),
    ("MIT CSAIL",         "Professor",               "researcher"),
    ("Stanford AI Lab",   "PhD Researcher",          "researcher"),
    ("CMU Robotics",      "Research Scientist",      "researcher"),
    ("UC Berkeley BAIR",  "Postdoc",                 "researcher"),
    ("ETH Zurich ASL",    "Research Engineer",       "researcher"),
    ("Toyota Research",   "Robotics Lead",           "enterprise"),
    ("Intrinsic (X)",     "Software Engineer",       "robot-startup"),
    ("Physical Intelligence", "ML Researcher",       "robot-startup"),
    ("Machina Labs",      "Head of AI",              "enterprise"),
]

DEMO_TIMES = [
    ("2027-03-18", ["10:00 AM", "11:00 AM", "2:00 PM", "3:00 PM"]),
    ("2027-03-19", ["9:30 AM", "10:30 AM", "1:00 PM", "3:30 PM", "4:30 PM"]),
    ("2027-03-20", ["10:00 AM", "11:00 AM", "2:00 PM", "3:00 PM", "4:00 PM"]),
    ("2027-03-21", ["9:30 AM", "10:30 AM", "1:30 PM"]),   # last day shorter
]


def generate_mock_data(seed: int = 42) -> tuple[list[DemoSlot], list[Registrant]]:
    rng = random.Random(seed)
    slots = []
    registrants = []
    slot_id = 1
    reg_id = 1

    # Generate all slots
    for date, times in DEMO_TIMES:
        for time_str in times:
            slot_type = "private" if rng.random() < 0.2 else "booth"
            slots.append(DemoSlot(
                slot_id=f"slot-{slot_id:03d}",
                date=date,
                time_str=time_str,
                duration_min=30 if slot_type == "private" else 15,
                slot_type=slot_type,
                available=True,
                registrant_id="",
            ))
            slot_id += 1

    # Add GTC talk slot
    slots.append(DemoSlot("slot-talk", "2027-03-19", "2:00 PM", 30, "talk", False, ""))

    # Register mock attendees
    companies_shuffled = list(COMPANIES)
    rng.shuffle(companies_shuffled)

    for i, (company, title, interest) in enumerate(companies_shuffled[:len(slots)-2]):
        if i >= len(slots) - 1: break
        slot = slots[i]
        slot.available = False
        slot.registrant_id = f"reg-{reg_id:03d}"

        name_first = rng.choice(["Alex", "Jordan", "Taylor", "Morgan", "Casey",
                                  "Riley", "Jamie", "Avery", "Quinn", "Drew"])
        name_last = rng.choice(["Chen", "Park", "Smith", "Johnson", "Kim",
                                 "Lee", "Wang", "Patel", "Garcia", "Brown"])

        registrants.append(Registrant(
            reg_id=f"reg-{reg_id:03d}",
            name=f"{name_first} {name_last}",
            company=company,
            title=title,
            interest=interest,
            slot_id=slot.slot_id,
            registered_at=f"2027-0{rng.randint(1,2)}-{rng.randint(10,28)}",
            confirmed=rng.random() > 0.15,
            notes="",
        ))
        reg_id += 1

    return slots, registrants


# ── HTML generator ────────────────────────────────────────────────────────────

def render_html(slots: list[DemoSlot], registrants: list[Registrant]) -> str:
    reg_by_slot = {r.slot_id: r for r in registrants}
    total = len(slots)
    booked = sum(1 for s in slots if not s.available)
    confirmed = sum(1 for r in registrants if r.confirmed)

    interest_counts: dict[str, int] = {}
    for r in registrants:
        interest_counts[r.interest] = interest_counts.get(r.interest, 0) + 1

    # SVG: registrant interest breakdown (horizontal bar chart)
    interest_colors = {
        "robot-startup": "#22c55e", "enterprise": "#3b82f6",
        "nvidia-team": "#C74634", "investor": "#f59e0b", "researcher": "#a855f7"
    }
    w_bar, h_bar = 380, 120
    max_count = max(interest_counts.values()) if interest_counts else 1
    svg_interest = f'<svg width="{w_bar}" height="{h_bar}" style="background:#0f172a;border-radius:8px">'
    for i, (interest, count) in enumerate(sorted(interest_counts.items(), key=lambda x: -x[1])):
        y = 10 + i * 22
        bw = count / max_count * (w_bar - 120)
        col = interest_colors.get(interest, "#64748b")
        svg_interest += (f'<rect x="110" y="{y}" width="{bw:.1f}" height="14" '
                         f'fill="{col}" rx="2" opacity="0.85"/>')
        svg_interest += (f'<text x="108" y="{y+11}" fill="#94a3b8" font-size="9.5" '
                         f'text-anchor="end">{interest.replace("-", " ")}</text>')
        svg_interest += (f'<text x="{113+bw:.1f}" y="{y+11}" fill="{col}" '
                         f'font-size="9">{count}</text>')
    svg_interest += '</svg>'

    # Schedule table
    schedule_rows = ""
    for date, _ in DEMO_TIMES:
        day_slots = [s for s in slots if s.date == date]
        for s in day_slots:
            r = reg_by_slot.get(s.slot_id)
            if s.available:
                status_cell = '<td style="color:#22c55e">Available</td><td colspan="3">—</td>'
            elif s.slot_type == "talk":
                status_cell = '<td style="color:#C74634">GTC Talk</td><td colspan="3">Public — 30min</td>'
            elif r:
                conf_col = "#22c55e" if r.confirmed else "#f59e0b"
                int_col = interest_colors.get(r.interest, "#94a3b8")
                status_cell = (f'<td style="color:{conf_col}">{"✓ Confirmed" if r.confirmed else "Pending"}</td>'
                               f'<td style="color:#e2e8f0">{r.name}</td>'
                               f'<td style="color:#94a3b8">{r.company}</td>'
                               f'<td style="color:{int_col}">{r.interest}</td>')
            else:
                status_cell = '<td style="color:#64748b">Booked</td><td colspan="3">—</td>'

            type_col = "#C74634" if s.slot_type == "private" else "#3b82f6"
            schedule_rows += (f'<tr><td style="color:#64748b">{s.date}</td>'
                              f'<td>{s.time_str}</td>'
                              f'<td>{s.duration_min}min</td>'
                              f'<td style="color:{type_col}">{s.slot_type}</td>'
                              f'{status_cell}</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>GTC 2027 Demo Registration — OCI Robot Cloud</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>GTC 2027 — OCI Robot Cloud Demo Registration</h1>
<div class="meta">March 18-21, 2027 · San Jose Convention Center · OCI Booth + 30-min Talk Track</div>

<div class="grid">
  <div class="card"><h3>Total Slots</h3>
    <div class="big">{total}</div></div>
  <div class="card"><h3>Booked</h3>
    <div class="big" style="color:#C74634">{booked}</div>
    <div style="color:#64748b;font-size:12px">{booked/total*100:.0f}% filled</div></div>
  <div class="card"><h3>Confirmed</h3>
    <div class="big" style="color:#22c55e">{confirmed}</div></div>
  <div class="card"><h3>Available</h3>
    <div class="big" style="color:#22c55e">{total-booked}</div></div>
</div>

<div class="layout">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Registrant Profiles</h3>
    {svg_interest}
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Top Companies</h3>
    <div style="display:flex;flex-direction:column;gap:4px">
      {''.join(f'<div style="font-size:12px;color:#94a3b8">{''.join(rr.company for rr in registrants[:3] if rr.company==c)}{c} — <span style=\'color:{interest_colors.get(registrants[[r.company for r in registrants].index(c)].interest,chr(35)+\"64748b\")}\'>{"×"+str(sum(1 for r in registrants if r.company==c))}</span></div>' for c in dict.fromkeys(r.company for r in registrants)[:8])}
    </div>
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Demo Schedule</h3>
<table>
  <tr><th>Date</th><th>Time</th><th>Duration</th><th>Type</th>
      <th>Status</th><th>Name</th><th>Company</th><th>Interest</th></tr>
  {schedule_rows}
</table>
</body></html>"""


# ── HTTP server ───────────────────────────────────────────────────────────────

def make_handler(slots, registrants):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass
        def do_GET(self):
            if self.path in ("/", "/register"):
                body = render_html(slots, registrants).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/registrants":
                data = [{"id": r.reg_id, "company": r.company, "interest": r.interest,
                          "confirmed": r.confirmed} for r in registrants]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404); self.end_headers()
    return Handler


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GTC 2027 demo registration portal")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--port",   type=int, default=8063)
    parser.add_argument("--output", default="")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    slots, registrants = generate_mock_data(args.seed)
    booked = sum(1 for s in slots if not s.available)
    print(f"[gtc-reg] {len(slots)} slots · {booked} booked · {len(registrants)} registrants")

    html = render_html(slots, registrants)
    if args.output:
        Path(args.output).write_text(html)
        print(f"[gtc-reg] HTML → {args.output}")
        return

    out = Path("/tmp/gtc_registration_portal.html")
    out.write_text(html)
    print(f"[gtc-reg] HTML → {out}")
    print(f"[gtc-reg] Serving on http://0.0.0.0:{args.port}")
    server = HTTPServer(("0.0.0.0", args.port), make_handler(slots, registrants))
    server.serve_forever()


if __name__ == "__main__":
    main()
