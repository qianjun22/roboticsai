#!/usr/bin/env python3
"""multi_customer_isolation_test.py — OCI Robot Cloud multi-tenant data isolation tests.

Verifies that customer datasets, checkpoints, API keys, GPU reservations,
training job namespaces, eval outputs, and serving endpoints are fully
isolated from one another. All tests are simulated (no live OCI calls).

Usage:
    python multi_customer_isolation_test.py [--output /tmp/isolation_test.html]
"""

import argparse
import hashlib
import itertools
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Customer:
    id: str
    name: str
    tier: str          # pilot | growth | enterprise
    dataset_path: str
    checkpoint_path: str
    api_key_hash: str


@dataclass
class IsolationTest:
    test_name: str
    customer_a: Customer
    customer_b: Customer
    passed: bool
    severity: str      # critical | high | medium
    detail: str


# ---------------------------------------------------------------------------
# Individual test functions
# ---------------------------------------------------------------------------

def test_dataset_path_isolation(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify dataset paths do not overlap or share a common prefix."""
    p1 = c1.dataset_path.rstrip("/")
    p2 = c2.dataset_path.rstrip("/")
    overlap = p1.startswith(p2 + "/") or p2.startswith(p1 + "/") or p1 == p2
    passed = not overlap
    detail = (
        "Dataset paths are fully separate."
        if passed
        else f"Path collision: '{p1}' and '{p2}' share a prefix."
    )
    return IsolationTest(
        test_name="dataset_path_isolation",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="critical",
        detail=detail,
    )


def test_checkpoint_namespace(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify checkpoint directories are in separate namespaces."""
    p1 = c1.checkpoint_path.rstrip("/")
    p2 = c2.checkpoint_path.rstrip("/")
    overlap = p1.startswith(p2 + "/") or p2.startswith(p1 + "/") or p1 == p2
    passed = not overlap
    detail = (
        "Checkpoint namespaces are isolated."
        if passed
        else f"Checkpoint namespace collision: '{p1}' vs '{p2}'."
    )
    return IsolationTest(
        test_name="checkpoint_namespace",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="critical",
        detail=detail,
    )


def test_api_key_collision(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify that API key hashes differ between customers."""
    passed = c1.api_key_hash != c2.api_key_hash
    detail = (
        "API key hashes are distinct."
        if passed
        else "COLLISION: both customers share the same API key hash."
    )
    return IsolationTest(
        test_name="api_key_collision",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="critical",
        detail=detail,
    )


def _mock_gpu_job_id(customer_id: str) -> str:
    """Deterministic mock GPU job ID derived from customer ID."""
    return f"gpu-job-{hashlib.md5(customer_id.encode()).hexdigest()[:8]}"


def test_gpu_scheduling_isolation(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify GPU job IDs don't conflict (mock: derived from customer ID)."""
    jid1 = _mock_gpu_job_id(c1.id)
    jid2 = _mock_gpu_job_id(c2.id)
    passed = jid1 != jid2
    detail = (
        f"GPU job IDs are unique: {jid1} vs {jid2}."
        if passed
        else f"GPU job ID collision detected: both map to {jid1}."
    )
    return IsolationTest(
        test_name="gpu_scheduling_isolation",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="high",
        detail=detail,
    )


def _mock_job_name(customer_id: str, job_type: str = "train") -> str:
    return f"{customer_id}-{job_type}-001"


def test_training_job_namespace(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify training job names are prefixed by customer ID and don't collide."""
    j1 = _mock_job_name(c1.id)
    j2 = _mock_job_name(c2.id)
    # Both must start with their own customer ID and must be different
    prefixed = j1.startswith(c1.id) and j2.startswith(c2.id)
    no_collision = j1 != j2
    passed = prefixed and no_collision
    if not prefixed:
        detail = "Job name missing customer-ID prefix."
    elif not no_collision:
        detail = f"Job name collision: both customers produce '{j1}'."
    else:
        detail = f"Job names correctly prefixed and distinct: {j1} vs {j2}."
    return IsolationTest(
        test_name="training_job_namespace",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="high",
        detail=detail,
    )


def _eval_output_dir(customer_id: str) -> str:
    return f"/oci/robot-cloud/eval/{customer_id}/results"


def test_eval_result_separation(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify eval output directories are separate per customer."""
    d1 = _eval_output_dir(c1.id)
    d2 = _eval_output_dir(c2.id)
    overlap = d1.startswith(d2 + "/") or d2.startswith(d1 + "/") or d1 == d2
    passed = not overlap
    detail = (
        f"Eval output dirs are separate: {d1} vs {d2}."
        if passed
        else f"Eval output dir collision: {d1} overlaps with {d2}."
    )
    return IsolationTest(
        test_name="eval_result_separation",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="medium",
        detail=detail,
    )


# Port allocation: pilot=8100–8199, growth=8200–8299, enterprise=8300–8399
_TIER_PORT_BASE = {"pilot": 8100, "growth": 8200, "enterprise": 8300}


def _mock_serving_port(customer: Customer) -> int:
    base = _TIER_PORT_BASE.get(customer.tier, 8400)
    # Deterministic offset within tier block using customer ID hash
    offset = int(hashlib.md5(customer.id.encode()).hexdigest()[:4], 16) % 100
    return base + offset


def test_model_serving_endpoint_isolation(c1: Customer, c2: Customer) -> IsolationTest:
    """Verify per-customer model serving ports don't collide."""
    p1 = _mock_serving_port(c1)
    p2 = _mock_serving_port(c2)
    passed = p1 != p2
    detail = (
        f"Serving ports are unique: {p1} ('{c1.name}') vs {p2} ('{c2.name}')."
        if passed
        else f"Port collision on {p1}: both '{c1.name}' and '{c2.name}' assigned the same port."
    )
    return IsolationTest(
        test_name="model_serving_endpoint_isolation",
        customer_a=c1,
        customer_b=c2,
        passed=passed,
        severity="high",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------

_TEST_FUNCTIONS = [
    test_dataset_path_isolation,
    test_checkpoint_namespace,
    test_api_key_collision,
    test_gpu_scheduling_isolation,
    test_training_job_namespace,
    test_eval_result_separation,
    test_model_serving_endpoint_isolation,
]


def run_isolation_matrix(customers: List[Customer]) -> List[IsolationTest]:
    """Run all pairwise isolation tests for every unique pair of customers."""
    results: List[IsolationTest] = []
    for c1, c2 in itertools.combinations(customers, 2):
        for fn in _TEST_FUNCTIONS:
            results.append(fn(c1, c2))
    return results


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

_SEVERITY_COLOR = {"critical": "#ef4444", "high": "#f97316", "medium": "#eab308"}
_SEVERITY_ORDER = ["critical", "high", "medium"]


def render_html(tests: List[IsolationTest], customers: List[Customer]) -> str:
    total = len(tests)
    passed_count = sum(1 for t in tests if t.passed)
    failed_count = total - passed_count
    all_passed = failed_count == 0

    banner_text = "ISOLATED" if all_passed else "BREACH DETECTED"
    banner_bg = "#16a34a" if all_passed else "#dc2626"

    # ------------------------------------------------------------------
    # Pairwise matrix SVG
    # ------------------------------------------------------------------
    n = len(customers)
    cell = 52
    label_w = 160
    svg_w = label_w + n * cell + 20
    svg_h = label_w + n * cell + 20

    def customer_pair_key(c1: Customer, c2: Customer):
        return (min(c1.id, c2.id), max(c1.id, c2.id))

    # Build pass/fail lookup per (pair, test_name)
    pair_results: dict = {}
    for t in tests:
        key = customer_pair_key(t.customer_a, t.customer_b)
        pair_results.setdefault(key, []).append(t.passed)

    # Aggregate: any failure → red
    pair_status: dict = {}
    for key, results_list in pair_results.items():
        pair_status[key] = all(results_list)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}">',
        f'<rect width="{svg_w}" height="{svg_h}" fill="#1e293b" rx="8"/>',
    ]

    # Column labels (rotated)
    for ci, c in enumerate(customers):
        x = label_w + ci * cell + cell // 2
        y = label_w - 8
        short = c.name.split()[0]
        svg_lines.append(
            f'<text x="{x}" y="{y}" fill="#94a3b8" font-size="11" '
            f'text-anchor="middle" font-family="monospace">{short}</text>'
        )

    # Row labels + cells
    for ri, cr in enumerate(customers):
        y_mid = label_w + ri * cell + cell // 2
        # Row label
        svg_lines.append(
            f'<text x="{label_w - 8}" y="{y_mid + 4}" fill="#94a3b8" font-size="11" '
            f'text-anchor="end" font-family="monospace">{cr.name.split()[0]}</text>'
        )
        for ci, cc in enumerate(customers):
            x = label_w + ci * cell
            y = label_w + ri * cell
            if ri == ci:
                fill = "#334155"
                label = "—"
                lc = "#64748b"
            else:
                key = customer_pair_key(cr, cc)
                ok = pair_status.get(key, True)
                fill = "#15803d" if ok else "#b91c1c"
                label = "✓" if ok else "✗"
                lc = "#bbf7d0" if ok else "#fecaca"
            svg_lines.append(
                f'<rect x="{x + 3}" y="{y + 3}" width="{cell - 6}" height="{cell - 6}" '
                f'fill="{fill}" rx="4"/>'
            )
            svg_lines.append(
                f'<text x="{x + cell // 2}" y="{y + cell // 2 + 5}" fill="{lc}" '
                f'font-size="16" text-anchor="middle" font-family="monospace">{label}</text>'
            )

    svg_lines.append("</svg>")
    matrix_svg = "\n".join(svg_lines)

    # ------------------------------------------------------------------
    # Severity breakdown cards
    # ------------------------------------------------------------------
    sev_cards_html = ""
    for sev in _SEVERITY_ORDER:
        sev_tests = [t for t in tests if t.severity == sev]
        sev_fail = sum(1 for t in sev_tests if not t.passed)
        color = _SEVERITY_COLOR[sev]
        icon = "✗" if sev_fail else "✓"
        icon_color = "#ef4444" if sev_fail else "#22c55e"
        sev_cards_html += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                    padding:16px 20px;min-width:180px;flex:1;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                      color:{color};margin-bottom:6px;">{sev}</div>
          <div style="font-size:28px;font-weight:700;color:#f1f5f9;">
            {icon_color and ''}<span style="color:{icon_color}">{icon}</span>
            &nbsp;{sev_fail}/{len(sev_tests)}
          </div>
          <div style="font-size:12px;color:#64748b;margin-top:4px;">failures</div>
        </div>"""

    # ------------------------------------------------------------------
    # Per-test detail table rows
    # ------------------------------------------------------------------
    table_rows = ""
    for t in tests:
        status_cell = (
            '<span style="color:#22c55e;font-weight:600;">PASS</span>'
            if t.passed
            else '<span style="color:#ef4444;font-weight:600;">FAIL</span>'
        )
        sev_color = _SEVERITY_COLOR.get(t.severity, "#94a3b8")
        pair_str = f"{t.customer_a.name} ↔ {t.customer_b.name}"
        table_rows += f"""
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#94a3b8;font-family:monospace;font-size:12px;">{t.test_name}</td>
          <td style="padding:10px 14px;color:#cbd5e1;font-size:13px;">{pair_str}</td>
          <td style="padding:10px 14px;">{status_cell}</td>
          <td style="padding:10px 14px;color:{sev_color};font-size:12px;text-transform:uppercase;">{t.severity}</td>
          <td style="padding:10px 14px;color:#94a3b8;font-size:12px;">{t.detail}</td>
        </tr>"""

    # ------------------------------------------------------------------
    # Customer summary rows
    # ------------------------------------------------------------------
    customer_rows = ""
    for c in customers:
        tier_colors = {"pilot": "#3b82f6", "growth": "#8b5cf6", "enterprise": "#f59e0b"}
        tc = tier_colors.get(c.tier, "#94a3b8")
        port = _mock_serving_port(c)
        customer_rows += f"""
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 14px;color:#f1f5f9;font-weight:600;">{c.name}</td>
          <td style="padding:10px 14px;color:{tc};font-size:12px;text-transform:uppercase;font-weight:600;">{c.tier}</td>
          <td style="padding:10px 14px;color:#94a3b8;font-family:monospace;font-size:11px;">{c.dataset_path}</td>
          <td style="padding:10px 14px;color:#94a3b8;font-family:monospace;font-size:11px;">{c.checkpoint_path}</td>
          <td style="padding:10px 14px;color:#64748b;font-family:monospace;font-size:11px;">{c.api_key_hash[:12]}…</td>
          <td style="padding:10px 14px;color:#94a3b8;font-family:monospace;">{port}</td>
        </tr>"""

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Multi-Customer Isolation Test Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      min-height: 100vh;
      padding: 32px 24px;
    }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f8fafc; }}
    h2 {{ font-size: 16px; font-weight: 600; color: #cbd5e1; margin-bottom: 12px; }}
    .section {{ margin-bottom: 36px; }}
    table {{ width: 100%; border-collapse: collapse; background: #0f172a; }}
    th {{ background: #1e293b; color: #64748b; font-size: 11px; text-transform: uppercase;
          letter-spacing: 0.08em; padding: 10px 14px; text-align: left; }}
    tr:hover td {{ background: #1a2640; }}
    .tag {{ display:inline-block; padding:2px 8px; border-radius:4px;
            font-size:11px; font-weight:600; text-transform:uppercase; }}
  </style>
</head>
<body>
  <!-- Header -->
  <div class="section" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;">
    <div>
      <h1>OCI Robot Cloud — Multi-Tenant Isolation Report</h1>
      <div style="color:#475569;font-size:13px;margin-top:4px;">Generated {timestamp}</div>
    </div>
    <div style="background:{banner_bg};color:#fff;font-size:20px;font-weight:800;
                letter-spacing:2px;padding:12px 32px;border-radius:8px;">
      {banner_text}
    </div>
  </div>

  <!-- Summary strip -->
  <div class="section" style="display:flex;gap:16px;flex-wrap:wrap;align-items:stretch;">
    <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:140px;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:6px;">Total Tests</div>
      <div style="font-size:28px;font-weight:700;color:#f1f5f9;">{total}</div>
    </div>
    <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:140px;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#22c55e;margin-bottom:6px;">Passed</div>
      <div style="font-size:28px;font-weight:700;color:#22c55e;">{passed_count}</div>
    </div>
    <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:140px;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#ef4444;margin-bottom:6px;">Failed</div>
      <div style="font-size:28px;font-weight:700;color:#ef4444;">{failed_count}</div>
    </div>
    {sev_cards_html}
  </div>

  <!-- Pairwise matrix -->
  <div class="section">
    <h2>Pairwise Isolation Matrix</h2>
    <div style="overflow-x:auto;">{matrix_svg}</div>
    <div style="margin-top:8px;font-size:12px;color:#475569;">
      Green cell = all tests pass for that pair. Red = at least one test failed.
    </div>
  </div>

  <!-- Customer inventory -->
  <div class="section">
    <h2>Registered Customers</h2>
    <div style="border:1px solid #1e293b;border-radius:8px;overflow:hidden;">
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Tier</th><th>Dataset Path</th>
            <th>Checkpoint Path</th><th>API Key Hash</th><th>Serving Port</th>
          </tr>
        </thead>
        <tbody>{customer_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Per-test detail table -->
  <div class="section">
    <h2>Test Detail</h2>
    <div style="border:1px solid #1e293b;border-radius:8px;overflow:hidden;">
      <table>
        <thead>
          <tr>
            <th>Test</th><th>Pair</th><th>Status</th><th>Severity</th><th>Detail</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="color:#334155;font-size:11px;text-align:center;margin-top:16px;">
    OCI Robot Cloud &mdash; Confidential &mdash; Simulated isolation checks only
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Mock customers
# ---------------------------------------------------------------------------

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


MOCK_CUSTOMERS: List[Customer] = [
    Customer(
        id="agility",
        name="Agility Robotics",
        tier="pilot",
        dataset_path="/oci/robot-cloud/datasets/agility/demo_v1",
        checkpoint_path="/oci/robot-cloud/checkpoints/agility",
        api_key_hash=_sha256("agility-secret-key-xk9z"),
    ),
    Customer(
        id="figure",
        name="Figure AI",
        tier="growth",
        dataset_path="/oci/robot-cloud/datasets/figure/humanoid_2k",
        checkpoint_path="/oci/robot-cloud/checkpoints/figure",
        api_key_hash=_sha256("figure-secret-key-m3qw"),
    ),
    Customer(
        id="boston",
        name="Boston Dynamics",
        tier="enterprise",
        dataset_path="/oci/robot-cloud/datasets/boston/spot_manipulation",
        checkpoint_path="/oci/robot-cloud/checkpoints/boston",
        api_key_hash=_sha256("boston-secret-key-r7vp"),
    ),
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud multi-tenant isolation test suite."
    )
    parser.add_argument(
        "--output",
        default="/tmp/isolation_test.html",
        help="Path for the HTML report (default: /tmp/isolation_test.html)",
    )
    args = parser.parse_args()

    customers = MOCK_CUSTOMERS
    print(f"Running isolation matrix for {len(customers)} customers …")
    tests = run_isolation_matrix(customers)

    passed = sum(1 for t in tests if t.passed)
    failed = len(tests) - passed
    print(f"  {len(tests)} tests executed — {passed} passed, {failed} failed")

    for t in tests:
        status = "PASS" if t.passed else "FAIL"
        print(
            f"  [{status}] [{t.severity.upper():8}] "
            f"{t.test_name}  |  {t.customer_a.name} ↔ {t.customer_b.name}"
        )

    html = render_html(tests, customers)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"\nReport written to: {out_path}")

    if failed > 0:
        print("RESULT: BREACH DETECTED — isolation failures found.", file=sys.stderr)
        return 1
    print("RESULT: ISOLATED — all tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
