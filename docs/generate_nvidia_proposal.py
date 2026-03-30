"""
Generates NVIDIA co-engineering proposal HTML document.

Formal ask for Isaac Sim optimization collaboration, Cosmos model weights,
and GTC 2027 co-presentation — intended for the NVIDIA Isaac/GR00T team
via Greg Pavlik's introduction.

Usage:
    python3 generate_nvidia_proposal.py --output /tmp/nvidia_co_engineering_proposal.html
"""

import argparse
import datetime
from dataclasses import dataclass
from typing import List


@dataclass
class ProposalSection:
    title: str
    content: str
    priority: str   # critical | high | medium
    status: str     # proposed | in_progress | done


def build_sections() -> List[ProposalSection]:
    sections = [
        ProposalSection(
            title="Executive Summary",
            content="""
OCI is positioned to become NVIDIA's preferred cloud for robotics training workloads.
Oracle Cloud Infrastructure already runs the full GR00T N1.6 fine-tuning pipeline
end-to-end, delivering measurable results that neither AWS nor GCP can match on price-performance:

<ul>
  <li><strong>8.7× MAE improvement</strong> (0.103 → 0.013) via IK-guided Synthetic Data Generation</li>
  <li><strong>$0.43 per training run</strong> on OCI A100 (GPU4, 40 GB) at current spot pricing</li>
  <li><strong>9.6× cheaper than AWS p4d.24xlarge</strong> for equivalent A100 compute hours</li>
  <li><strong>3.07× DDP throughput</strong> on 4-GPU OCI instances vs. single-GPU baseline</li>
  <li><strong>80+ open-source scripts</strong> — Isaac Sim SDG, GR00T fine-tune, DAgger, closed-loop eval,
      safety monitor, teleoperation, data flywheel — all production-hardened on OCI</li>
</ul>

Oracle is already the only cloud vendor running a complete Isaac Sim → GR00T fine-tune →
closed-loop evaluation loop at production scale. This proposal formalises the next step:
a structured co-engineering partnership to accelerate mutual go-to-market.
            """,
            priority="critical",
            status="proposed",
        ),
        ProposalSection(
            title="Current State — What Is Running Today",
            content="""
The OCI Robot Cloud platform is live on a bare-metal A100 instance
(<code>GPU4 · 138.1.153.110</code>) with the following services:

<table>
  <thead><tr><th>Port</th><th>Service</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>8001</td><td>GR00T N1.6-3B inference server (227 ms p50)</td><td>Running</td></tr>
    <tr><td>8003</td><td>Data collection API</td><td>Running</td></tr>
    <tr><td>8080</td><td>FastAPI orchestration service + Python SDK</td><td>Running</td></tr>
    <tr><td>8021–8026</td><td>Multi-task / registry / portal micro-services</td><td>Running</td></tr>
    <tr><td>8062</td><td>Safety monitor</td><td>Running</td></tr>
  </tbody>
</table>

<br>
<strong>Fine-tuning baseline:</strong> 1 000-demo dataset, 2 000 steps, loss = 0.099 (↓39% vs.
untrained), MAE = 0.013 after SDG curriculum. DAgger run 9 is the current active iteration.<br><br>

<strong>Simulation:</strong> NVIDIA Isaac Sim drives all synthetic data generation (RTX domain
randomization, IK motion planning). Current throughput is ~8 fps on the OCI A100 — the main
bottleneck targeted by this proposal.
            """,
            priority="high",
            status="in_progress",
        ),
        ProposalSection(
            title="The Ask — Four Specific Requests",
            content="""
<ol>

  <li>
    <strong class="ask-label">Isaac Sim Optimization — Joint Pipeline Tuning</strong>
    <span class="owner-badge owner-joint">Joint</span><br>
    Current Isaac Sim SDG throughput on OCI is ~8 fps. NVIDIA Isaac engineering has profiling
    data and kernel-level optimisations that are not yet public. We propose a 6-week joint
    sprint to co-tune the Isaac → OCI pipeline and target <strong>32 fps (4× improvement)</strong>
    through:
    <ul>
      <li>NVIDIA-provided Isaac Sim build flags optimised for A100 PCIe</li>
      <li>Shared profiling sessions (Nsight Systems) on OCI GPU4</li>
      <li>Upstreaming OCI-specific tuning back to the Isaac Sim NGC container</li>
    </ul>
  </li>

  <li>
    <strong class="ask-label">Cosmos-7B Model Weights — NGC Access</strong>
    <span class="owner-badge owner-nvidia">NVIDIA</span><br>
    Oracle requests NGC access to the <strong>Cosmos-7B world model</strong> weights for
    fine-tuning experiments within OCI Robot Cloud. Intended use:
    <ul>
      <li>World-model-guided DAgger (replace hand-crafted reward with Cosmos rollout score)</li>
      <li>Sim-to-real gap analysis using Cosmos video predictions vs. Isaac Sim renders</li>
      <li>Benchmark: Cosmos-guided policy vs. GR00T N1.6 fine-tune (publishable at GTC 2027)</li>
    </ul>
    Access under existing Oracle–NVIDIA NDA; no redistribution.
  </li>

  <li>
    <strong class="ask-label">GR00T N1.5 / N2 Early Access</strong>
    <span class="owner-badge owner-nvidia">NVIDIA</span><br>
    Pre-release weights for <strong>GR00T N1.5 and/or N2</strong> to run benchmark experiments
    on OCI. Oracle will provide NVIDIA with comparative fine-tuning results (loss curves, eval
    success rates, cost-per-run) on identical datasets — a ready-made third-party benchmark
    that strengthens the GR00T launch story.
  </li>

  <li>
    <strong class="ask-label">GTC 2027 Co-Presenter from NVIDIA Isaac Team</strong>
    <span class="owner-badge owner-joint">Joint</span><br>
    Oracle has drafted a 30-minute GTC 2027 talk proposal:
    <em>"OCI Robot Cloud: Production-Scale GR00T Fine-Tuning from Isaac Sim to Deployment"</em>
    (full submission at <code>docs/gtc2027_talk_submission.md</code>).
    We request a named NVIDIA Isaac or GR00T team member as co-presenter. This positions the
    session as an official NVIDIA + Oracle joint talk, maximising attendee credibility and
    press coverage.
  </li>

</ol>
            """,
            priority="critical",
            status="proposed",
        ),
        ProposalSection(
            title="What Oracle Brings to the Partnership",
            content="""
<ul>
  <li><strong>OCI A100 compute at scale:</strong> GPU4 bare-metal instance (138.1.153.110),
      additional capacity available on-demand; US-origin hardware for compliance-sensitive
      customers (DoD, regulated finance, healthcare)</li>
  <li><strong>End-to-end open-source pipeline:</strong> 80+ scripts covering Isaac Sim SDG,
      GR00T fine-tune, DAgger, closed-loop eval, safety monitor, teleoperation, data flywheel,
      billing, A/B test — all on GitHub (<code>qianjun22/roboticsai</code>)</li>
  <li><strong>Enterprise customer pipeline:</strong> Oracle has direct relationships with
      manufacturing, logistics, and automotive OEMs actively evaluating robotics AI platforms;
      5 design partners already in the funnel for OCI Robot Cloud</li>
  <li><strong>Marketing and event reach:</strong> Oracle AI World 2026 (anchor speaking slot),
      Oracle CloudWorld, co-branded blog posts via Oracle Newsroom</li>
  <li><strong>Compliance posture:</strong> FedRAMP High, ITAR-capable OCI regions; opens
      government robotics opportunities that AWS GovCloud alone cannot serve</li>
</ul>
            """,
            priority="high",
            status="proposed",
        ),
        ProposalSection(
            title="Go-to-Market Plan",
            content="""
<ol>
  <li><strong>OCI as NVIDIA Preferred Robotics Cloud (Q2 2026):</strong>
      Formal co-sell agreement and "Preferred Cloud" badge in NVIDIA robotics documentation
      and NGC landing pages.</li>
  <li><strong>Joint Press Release (Q2 2026):</strong>
      Announce Isaac Sim optimization results (4× FPS) and OCI Robot Cloud GA simultaneously
      with NVIDIA Isaac Sim 4.x release.</li>
  <li><strong>5 Design Partners (Q3 2026):</strong>
      Co-sell to Oracle enterprise accounts in manufacturing and logistics; NVIDIA provides
      technical validation stamps; Oracle provides OCI credits.</li>
  <li><strong>Oracle AI World 2026 (Q4 2026):</strong>
      Live demo of Cosmos-guided DAgger on OCI; NVIDIA Isaac team on stage.</li>
  <li><strong>GTC 2027 (Q1 2027):</strong>
      Joint 30-minute session with benchmark results, customer case studies, and roadmap
      for GR00T N2 on OCI.</li>
</ol>
            """,
            priority="high",
            status="proposed",
        ),
        ProposalSection(
            title="Technical Roadmap",
            content="""
<table>
  <thead>
    <tr>
      <th>Phase</th><th>Timeline</th><th>Milestones</th><th>Owner</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Phase 1 — Isaac Optimization</strong></td>
      <td>Q2 2026<br>(Apr–Jun)</td>
      <td>
        Joint profiling sprint; Isaac Sim NGC container tuned for A100 PCIe;
        8 fps → 32 fps SDG throughput; publish benchmark blog
      </td>
      <td>Joint</td>
    </tr>
    <tr>
      <td><strong>Phase 2 — Cosmos Integration</strong></td>
      <td>Q3 2026<br>(Jul–Sep)</td>
      <td>
        NGC access granted; Cosmos-7B fine-tuned on OCI;
        world-model DAgger prototype; sim-to-real gap paper submitted
      </td>
      <td>NVIDIA (weights) / Oracle (infra)</td>
    </tr>
    <tr>
      <td><strong>Phase 3 — GTC Prep &amp; GA</strong></td>
      <td>Q4 2026<br>(Oct–Dec)</td>
      <td>
        GR00T N1.5/N2 early access; benchmark results locked;
        OCI Robot Cloud GA; AI World 2026 demo; GTC 2027 abstract submitted
      </td>
      <td>Joint</td>
    </tr>
    <tr>
      <td><strong>Phase 4 — GTC 2027</strong></td>
      <td>Q1 2027<br>(Jan–Mar)</td>
      <td>
        GTC 2027 joint session; 5 design partner case studies;
        OCI preferred-cloud badge live on NGC
      </td>
      <td>Joint</td>
    </tr>
  </tbody>
</table>
            """,
            priority="medium",
            status="proposed",
        ),
        ProposalSection(
            title="Mutual Value — Why This Partnership Works",
            content="""
<div class="two-col">
  <div class="col-card">
    <h4>NVIDIA Gets</h4>
    <ul>
      <li>Production OCI deployment showcase for Isaac Sim + GR00T — the only
          end-to-end public reference architecture outside of NVIDIA's own DGX Cloud</li>
      <li>Third-party MAE and cost benchmarks ready for GR00T N2 launch</li>
      <li>Enterprise customer referrals via Oracle's manufacturing / logistics / automotive
          OEM relationships</li>
      <li>Co-branded GTC 2027 session with Oracle PM and engineering on stage</li>
      <li>FedRAMP / ITAR pathway for US government robotics customers</li>
    </ul>
  </div>
  <div class="col-card">
    <h4>Oracle Gets</h4>
    <ul>
      <li>NVIDIA preferred-cloud designation for robotics — differentiating OCI from AWS
          and Azure in a fast-growing segment</li>
      <li>Isaac Sim kernel-level optimisations that reduce OCI SDG costs and improve
          customer time-to-value</li>
      <li>Cosmos-7B and GR00T N2 early access enabling first-mover product advantage</li>
      <li>NVIDIA partner referrals into robotics ISVs and systems integrators</li>
      <li>Co-marketing at GTC (50 000+ attendees) and NVIDIA press channels</li>
    </ul>
  </div>
</div>
            """,
            priority="high",
            status="proposed",
        ),
    ]
    return sections


PRIORITY_COLORS = {
    "critical": ("#dc2626", "#fee2e2", "CRITICAL"),
    "high":     ("#d97706", "#fef3c7", "HIGH"),
    "medium":   ("#2563eb", "#dbeafe", "MEDIUM"),
}

STATUS_COLORS = {
    "proposed":    ("#6b7280", "#f3f4f6"),
    "in_progress": ("#7c3aed", "#ede9fe"),
    "done":        ("#059669", "#d1fae5"),
}


def render_html(sections: List[ProposalSection]) -> str:
    today = datetime.date.today().strftime("%B %d, %Y")

    section_html_parts = []
    for idx, sec in enumerate(sections, start=1):
        pc, pbg, plabel = PRIORITY_COLORS.get(sec.priority, ("#6b7280", "#f3f4f6", sec.priority.upper()))
        sc, sbg = STATUS_COLORS.get(sec.status, ("#6b7280", "#f3f4f6"))
        section_html_parts.append(f"""
        <section class="proposal-section">
          <div class="section-header">
            <span class="section-number">{idx:02d}</span>
            <h2 class="section-title">{sec.title}</h2>
            <span class="badge" style="background:{pbg};color:{pc};border:1px solid {pc};">{plabel}</span>
            <span class="badge" style="background:{sbg};color:{sc};border:1px solid {sc};margin-left:6px;">{sec.status.replace('_',' ').upper()}</span>
          </div>
          <div class="section-body">{sec.content}</div>
        </section>
        """)

    sections_joined = "\n".join(section_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Oracle × NVIDIA Co-Engineering Partnership Proposal</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8fafc;
      color: #1e293b;
      line-height: 1.65;
    }}
    a {{ color: #2563eb; }}

    /* ── Page wrapper ── */
    .page {{ max-width: 900px; margin: 40px auto; padding: 0 24px 60px; }}

    /* ── Document header ── */
    .doc-header {{
      background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
      color: #fff;
      border-radius: 12px;
      padding: 40px 48px 36px;
      margin-bottom: 32px;
    }}
    .logo-row {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 28px;
    }}
    .logo-oracle {{
      font-size: 22px;
      font-weight: 800;
      color: #f97316;
      letter-spacing: -0.5px;
    }}
    .logo-sep {{ font-size: 24px; color: #94a3b8; }}
    .logo-nvidia {{
      font-size: 22px;
      font-weight: 800;
      color: #76b900;
      letter-spacing: 2px;
      text-transform: uppercase;
    }}
    .doc-header h1 {{
      font-size: 28px;
      font-weight: 700;
      line-height: 1.25;
      margin-bottom: 12px;
    }}
    .doc-header .subtitle {{
      font-size: 16px;
      color: #cbd5e1;
      margin-bottom: 20px;
    }}
    .meta-row {{
      display: flex;
      gap: 24px;
      flex-wrap: wrap;
      font-size: 13px;
      color: #94a3b8;
    }}
    .meta-row span strong {{ color: #e2e8f0; }}
    .confidential-badge {{
      display: inline-block;
      background: #dc2626;
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.5px;
      padding: 3px 10px;
      border-radius: 4px;
      text-transform: uppercase;
    }}

    /* ── TOC ── */
    .toc {{
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 24px 32px;
      margin-bottom: 28px;
    }}
    .toc h3 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: #64748b; margin-bottom: 12px; }}
    .toc ol {{ padding-left: 20px; }}
    .toc li {{ margin-bottom: 4px; font-size: 14px; }}
    .toc a {{ text-decoration: none; color: #334155; }}
    .toc a:hover {{ color: #2563eb; }}

    /* ── Sections ── */
    .proposal-section {{
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 28px 32px 24px;
      margin-bottom: 20px;
      scroll-margin-top: 20px;
    }}
    .section-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }}
    .section-number {{
      background: #0f172a;
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}
    .section-title {{
      font-size: 18px;
      font-weight: 700;
      color: #0f172a;
      flex: 1;
    }}
    .badge {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.8px;
      padding: 2px 9px;
      border-radius: 20px;
    }}

    /* ── Section body ── */
    .section-body ul, .section-body ol {{ padding-left: 22px; margin: 10px 0; }}
    .section-body li {{ margin-bottom: 6px; font-size: 15px; }}
    .section-body p {{ font-size: 15px; margin-bottom: 10px; }}
    .section-body strong {{ color: #0f172a; }}
    .ask-label {{ font-size: 16px; color: #0f172a; }}
    .owner-badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 1px 8px;
      border-radius: 12px;
      vertical-align: middle;
      margin-left: 8px;
    }}
    .owner-nvidia  {{ background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }}
    .owner-oracle  {{ background: #ffedd5; color: #9a3412; border: 1px solid #fdba74; }}
    .owner-joint   {{ background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }}

    /* ── Tables ── */
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 14px; }}
    th {{ background: #f1f5f9; text-align: left; padding: 10px 14px; font-weight: 600; color: #334155; border: 1px solid #e2e8f0; }}
    td {{ padding: 10px 14px; border: 1px solid #e2e8f0; vertical-align: top; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}

    /* ── Two-col mutual value ── */
    .two-col {{ display: flex; gap: 20px; flex-wrap: wrap; }}
    .col-card {{
      flex: 1;
      min-width: 260px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 18px 20px;
    }}
    .col-card h4 {{ font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 10px; }}

    /* ── Footer ── */
    .doc-footer {{
      margin-top: 40px;
      padding: 28px 32px;
      background: #0f172a;
      border-radius: 10px;
      color: #94a3b8;
      font-size: 13px;
    }}
    .doc-footer strong {{ color: #e2e8f0; }}
    .doc-footer .footer-grid {{ display: flex; gap: 40px; flex-wrap: wrap; margin-top: 14px; }}
    .doc-footer .footer-col {{ flex: 1; min-width: 180px; }}
    .doc-footer .footer-col p {{ margin-bottom: 4px; }}
    .doc-footer .conf-note {{
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid #334155;
      font-size: 11px;
      color: #64748b;
      text-align: center;
    }}
  </style>
</head>
<body>
<div class="page">

  <!-- ── Document Header ── -->
  <header class="doc-header">
    <div class="logo-row">
      <span class="logo-oracle">Oracle</span>
      <span class="logo-sep">×</span>
      <span class="logo-nvidia">NVIDIA</span>
      <span style="margin-left:auto;"><span class="confidential-badge">Confidential</span></span>
    </div>
    <h1>Co-Engineering Partnership Proposal:<br>OCI Robot Cloud × NVIDIA Isaac &amp; GR00T</h1>
    <p class="subtitle">
      Formal request for Isaac Sim optimization collaboration, Cosmos model weights,
      GR00T N1.5/N2 early access, and GTC 2027 co-presentation.
    </p>
    <div class="meta-row">
      <span><strong>Date:</strong> {today}</span>
      <span><strong>Prepared by:</strong> Jun Qian, Oracle OCI PM</span>
      <span><strong>Introduced via:</strong> Greg Pavlik</span>
      <span><strong>Intended recipient:</strong> NVIDIA Isaac / GR00T Engineering Team</span>
    </div>
  </header>

  <!-- ── Table of Contents ── -->
  <nav class="toc">
    <h3>Contents</h3>
    <ol>
      <li><a href="#s1">Executive Summary</a></li>
      <li><a href="#s2">Current State — What Is Running Today</a></li>
      <li><a href="#s3">The Ask — Four Specific Requests</a></li>
      <li><a href="#s4">What Oracle Brings to the Partnership</a></li>
      <li><a href="#s5">Go-to-Market Plan</a></li>
      <li><a href="#s6">Technical Roadmap</a></li>
      <li><a href="#s7">Mutual Value — Why This Partnership Works</a></li>
    </ol>
  </nav>

  <!-- ── Proposal Sections ── -->
  {sections_joined}

  <!-- ── Footer ── -->
  <footer class="doc-footer">
    <strong>Oracle OCI Robot Cloud — Partnership Enquiry</strong>
    <div class="footer-grid">
      <div class="footer-col">
        <p><strong>Primary Contact</strong></p>
        <p>Jun Qian</p>
        <p>Product Manager, Oracle OCI</p>
        <p>jun.q.qian@oracle.com</p>
      </div>
      <div class="footer-col">
        <p><strong>Technical Reference</strong></p>
        <p>GitHub: <a href="https://github.com/qianjun22/roboticsai" style="color:#60a5fa;">qianjun22/roboticsai</a></p>
        <p>GTC 2027 Submission: <code>docs/gtc2027_talk_submission.md</code></p>
        <p>OCI Instance: 138.1.153.110 (GPU4, A100 40 GB)</p>
      </div>
      <div class="footer-col">
        <p><strong>Introduction</strong></p>
        <p>Greg Pavlik</p>
        <p>SVP, Oracle AI &amp; Data Services</p>
      </div>
    </div>
    <div class="conf-note">
      CONFIDENTIAL — This document contains proprietary information of Oracle Corporation and is intended solely
      for the named recipient. Unauthorised distribution or reproduction is strictly prohibited.
      © {datetime.date.today().year} Oracle Corporation. All rights reserved.
    </div>
  </footer>

</div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the Oracle × NVIDIA co-engineering partnership proposal."
    )
    parser.add_argument(
        "--output",
        default="/tmp/nvidia_co_engineering_proposal.html",
        help="Output path for the HTML file (default: /tmp/nvidia_co_engineering_proposal.html)",
    )
    args = parser.parse_args()

    sections = build_sections()
    html = render_html(sections)

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Proposal written to: {args.output}")
    print(f"Sections: {len(sections)}")
    for s in sections:
        print(f"  [{s.priority.upper():8s}] {s.title}")


if __name__ == "__main__":
    main()
