#!/usr/bin/env python3
"""
OCI Robot Cloud — Enterprise Security Audit Report Generator
Covers API security, data handling, network, access control, compliance, and incident response.
Required for enterprise/gov cloud sales engagements.

Usage:
    python security_audit_report.py --mock --output /tmp/security_audit_report.html --seed 42
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

CATEGORIES = [
    "api_security",
    "data_handling",
    "network",
    "access_control",
    "compliance",
    "incident_response",
]

CATEGORY_LABELS = {
    "api_security": "API Security",
    "data_handling": "Data Handling",
    "network": "Network",
    "access_control": "Access Control",
    "compliance": "Compliance",
    "incident_response": "Incident Response",
}

SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 8, "low": 3}
SEVERITY_FAIL_PENALTIES = {"critical": -50, "high": -25, "medium": -10, "low": -3}


@dataclass
class SecurityCheck:
    check_id: str
    category: str  # api_security / data_handling / network / access_control / compliance / incident_response
    name: str
    description: str
    status: str  # pass / fail / warning / na
    severity: str  # critical / high / medium / low
    evidence: str
    remediation: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Check generation
# ---------------------------------------------------------------------------

def generate_security_checks(seed: int = 42) -> List[SecurityCheck]:
    rng = random.Random(seed)

    def _pick(items):
        return items[rng.randint(0, len(items) - 1)]

    def _status(weights):
        """weights: list of (status, weight)"""
        choices, ws = zip(*weights)
        r = rng.random() * sum(ws)
        acc = 0
        for c, w in zip(choices, ws):
            acc += w
            if r <= acc:
                return c
        return choices[-1]

    checks = []

    # ------------------------------------------------------------------ API Security
    api_checks = [
        SecurityCheck(
            check_id="API-001",
            category="api_security",
            name="HMAC Request Signing",
            description="All inbound API requests are validated with HMAC-SHA256 signatures to prevent tampering.",
            status=_status([("pass", 85), ("warning", 10), ("fail", 5)]),
            severity="critical",
            evidence="HMAC middleware active on /v1/* routes; signature header X-ORC-Signature enforced.",
            remediation="Enable HMAC signing for all remaining legacy endpoints under /v0/.",
        ),
        SecurityCheck(
            check_id="API-002",
            category="api_security",
            name="Rate Limiting",
            description="Per-tenant rate limits enforced at the API gateway (100 req/s default, configurable).",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="high",
            evidence="OCI API Gateway policy: 100 req/s with burst 200; 429 responses verified in load tests.",
            remediation="Apply rate-limit policy to admin endpoints; current admin API has no cap.",
        ),
        SecurityCheck(
            check_id="API-003",
            category="api_security",
            name="TLS 1.2+ Enforcement",
            description="All API traffic encrypted with TLS 1.2 minimum; TLS 1.0/1.1 disabled.",
            status=_status([("pass", 90), ("warning", 8), ("fail", 2)]),
            severity="critical",
            evidence="nmap TLS scan confirms TLS 1.2/1.3 only; cipher suites restricted to ECDHE+AES-GCM.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="API-004",
            category="api_security",
            name="JWT Expiry Policy",
            description="JWT access tokens expire within 1 hour; refresh tokens expire within 24 hours.",
            status=_status([("pass", 80), ("warning", 12), ("fail", 8)]),
            severity="high",
            evidence="Token TTL: access=3600s, refresh=86400s. Verified via decoded JWT claims.",
            remediation="Reduce refresh token lifetime to 12h for gov-cloud tenants.",
        ),
        SecurityCheck(
            check_id="API-005",
            category="api_security",
            name="API Key Rotation",
            description="API keys must be rotated every 90 days; automated rotation reminders sent at 75 days.",
            status=_status([("pass", 70), ("warning", 20), ("fail", 10)]),
            severity="high",
            evidence="Key rotation policy active; 3/47 partner keys are overdue (91-105 days old).",
            remediation="Force-rotate the 3 overdue keys and notify affected partners.",
        ),
        SecurityCheck(
            check_id="API-006",
            category="api_security",
            name="Input Validation & Schema Enforcement",
            description="All API inputs validated against JSON Schema; malformed requests rejected with 400.",
            status=_status([("pass", 85), ("warning", 10), ("fail", 5)]),
            severity="medium",
            evidence="OpenAPI spec with required field validation; fuzz tests show 0 schema bypasses.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="API-007",
            category="api_security",
            name="API Versioning & Deprecation",
            description="Breaking changes gated behind versioned endpoints; deprecated endpoints disabled after 6 months.",
            status=_status([("pass", 75), ("warning", 20), ("fail", 5)]),
            severity="low",
            evidence="v0 endpoints deprecated 2025-10-01; decommission scheduled 2026-04-01.",
            remediation="Accelerate v0 decommission if FedRAMP audit requires clean endpoint surface.",
        ),
        SecurityCheck(
            check_id="API-008",
            category="api_security",
            name="Secrets in API Responses",
            description="API responses must not leak internal tokens, credentials, or stack traces.",
            status=_status([("pass", 90), ("warning", 8), ("fail", 2)]),
            severity="critical",
            evidence="Automated secret-scan on response fixtures: 0 findings. Error handler returns generic messages.",
            remediation=None,
        ),
    ]

    # ------------------------------------------------------------------ Data Handling
    data_checks = [
        SecurityCheck(
            check_id="DATA-001",
            category="data_handling",
            name="Encryption at Rest (AES-256)",
            description="All robot telemetry, model weights, and customer data encrypted at rest using AES-256.",
            status=_status([("pass", 90), ("warning", 8), ("fail", 2)]),
            severity="critical",
            evidence="OCI Block Storage: Always Encrypted; OCI Object Storage: SSE-KMS with customer-managed keys.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="DATA-002",
            category="data_handling",
            name="PII Detection & Masking",
            description="Automated PII scanner runs on uploaded datasets; PII fields masked before storage.",
            status=_status([("pass", 75), ("warning", 18), ("fail", 7)]),
            severity="high",
            evidence="PII scanner v2.1 integrated in data ingestion pipeline; last scan: 2026-03-28.",
            remediation="Extend PII scanner to cover unstructured text fields in partner metadata.",
        ),
        SecurityCheck(
            check_id="DATA-003",
            category="data_handling",
            name="Data Residency — US Only",
            description="All customer data and model checkpoints stored exclusively in US OCI regions.",
            status=_status([("pass", 92), ("warning", 6), ("fail", 2)]),
            severity="critical",
            evidence="Terraform region lock: us-ashburn-1, us-phoenix-1, us-chicago-1. Cross-region replication disabled.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="DATA-004",
            category="data_handling",
            name="Data Retention Policy",
            description="Telemetry retained for 90 days; model checkpoints for 1 year; audit logs for 7 years.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="medium",
            evidence="OCI Object Lifecycle policies enforced; spot-check of 10 buckets shows compliant TTLs.",
            remediation="Apply lifecycle policy to 2 buckets missing TTL configuration.",
        ),
        SecurityCheck(
            check_id="DATA-005",
            category="data_handling",
            name="Audit Log Integrity",
            description="Audit logs are append-only, tamper-evident, and shipped to immutable OCI Audit service.",
            status=_status([("pass", 88), ("warning", 10), ("fail", 2)]),
            severity="high",
            evidence="OCI Audit service enabled; log export to Object Storage with WORM policy; HMAC verified.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="DATA-006",
            category="data_handling",
            name="Data Minimization",
            description="Only data required for training/inference is collected; optional telemetry fields are opt-in.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="medium",
            evidence="Data collection manifest reviewed; 3 optional fields confirmed as opt-in in SDK docs.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="DATA-007",
            category="data_handling",
            name="Cross-Tenant Data Isolation",
            description="Tenant data namespaced by compartment; queries scoped to requesting tenant's compartment.",
            status=_status([("pass", 88), ("warning", 10), ("fail", 2)]),
            severity="critical",
            evidence="OCI Compartment RBAC enforced at IAM layer; integration tests confirm no cross-tenant leakage.",
            remediation=None,
        ),
    ]

    # ------------------------------------------------------------------ Network
    network_checks = [
        SecurityCheck(
            check_id="NET-001",
            category="network",
            name="VPN Access for Admin Interfaces",
            description="Admin dashboards and management APIs accessible only via Oracle VPN.",
            status=_status([("pass", 85), ("warning", 12), ("fail", 3)]),
            severity="critical",
            evidence="Security list: admin ports (8080, 8081) whitelist only VPN CIDR 10.0.0.0/8.",
            remediation="Extend VPN requirement to port 8082 (training monitor) which is currently public.",
        ),
        SecurityCheck(
            check_id="NET-002",
            category="network",
            name="IP Allowlist for Partner APIs",
            description="Partner API access restricted to declared IP ranges; unknown IPs rejected.",
            status=_status([("pass", 78), ("warning", 17), ("fail", 5)]),
            severity="high",
            evidence="OCI WAF IP allowlist active for /v1/partner/* routes; 47 partner CIDR blocks registered.",
            remediation="3 partners have stale IP ranges — request updated CIDRs or suspend access.",
        ),
        SecurityCheck(
            check_id="NET-003",
            category="network",
            name="No Public Write Endpoints",
            description="Write operations (training triggers, data upload) not exposed on public internet.",
            status=_status([("pass", 88), ("warning", 10), ("fail", 2)]),
            severity="critical",
            evidence="Load balancer rule: POST/PUT/DELETE to /v1/* blocked from non-VPN/non-allowlisted sources.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="NET-004",
            category="network",
            name="DDoS Protection",
            description="OCI Shield DDoS protection active on all public-facing load balancers.",
            status=_status([("pass", 90), ("warning", 8), ("fail", 2)]),
            severity="high",
            evidence="OCI DDoS protection tier: Standard (automatic); WAF rate-limiting as secondary layer.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="NET-005",
            category="network",
            name="Network Segmentation",
            description="Production, staging, and dev environments on separate VCNs with no cross-env peering.",
            status=_status([("pass", 85), ("warning", 12), ("fail", 3)]),
            severity="high",
            evidence="VCN topology diagram reviewed; 3 VCNs (prod/stage/dev) with dedicated security lists.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="NET-006",
            category="network",
            name="Egress Traffic Control",
            description="Egress from compute instances restricted to known destinations via NAT gateway.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="medium",
            evidence="Security list: egress rules enumerate allowed endpoints; default-deny not yet enforced.",
            remediation="Switch egress to default-deny with explicit allowlist for registry, OCI services, NTP.",
        ),
    ]

    # ------------------------------------------------------------------ Access Control
    access_checks = [
        SecurityCheck(
            check_id="AC-001",
            category="access_control",
            name="Role-Based Access Control (RBAC)",
            description="All users assigned to roles (viewer/operator/admin/superadmin); no direct permission grants.",
            status=_status([("pass", 85), ("warning", 12), ("fail", 3)]),
            severity="critical",
            evidence="OCI IAM policies reviewed; 0 users with wildcard permissions; 4-tier role hierarchy enforced.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="AC-002",
            category="access_control",
            name="Partner Tenant Isolation",
            description="Each partner tenant cannot read, write, or list resources belonging to other tenants.",
            status=_status([("pass", 90), ("warning", 8), ("fail", 2)]),
            severity="critical",
            evidence="Penetration test (2026-02-15): 0 cross-tenant access findings. Compartment policy verified.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="AC-003",
            category="access_control",
            name="Principle of Least Privilege",
            description="Service accounts and compute instances have minimal permissions needed for their function.",
            status=_status([("pass", 78), ("warning", 17), ("fail", 5)]),
            severity="high",
            evidence="IAM audit: 2 service accounts have broad object-storage read across all buckets — excessive.",
            remediation="Scope those 2 service accounts to specific buckets required for their workload.",
        ),
        SecurityCheck(
            check_id="AC-004",
            category="access_control",
            name="MFA for Admin Accounts",
            description="All admin and operator accounts require multi-factor authentication.",
            status=_status([("pass", 88), ("warning", 10), ("fail", 2)]),
            severity="critical",
            evidence="OCI IAM MFA enforced via policy; 100% admin accounts show MFA devices enrolled.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="AC-005",
            category="access_control",
            name="Privileged Access Reviews",
            description="Quarterly review of all users with admin or elevated permissions.",
            status=_status([("pass", 75), ("warning", 18), ("fail", 7)]),
            severity="medium",
            evidence="Last access review: 2025-12-15. Next due 2026-03-15 — currently overdue by 14 days.",
            remediation="Complete Q1 access review; revoke stale accounts identified in Q4 review.",
        ),
        SecurityCheck(
            check_id="AC-006",
            category="access_control",
            name="SSH Key Management",
            description="SSH access to compute instances via key pairs only; password auth disabled.",
            status=_status([("pass", 88), ("warning", 10), ("fail", 2)]),
            severity="high",
            evidence="OCI instance metadata: PasswordAuthentication=no confirmed on all 12 prod instances.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="AC-007",
            category="access_control",
            name="Service Account Credential Rotation",
            description="Service account API keys rotated every 90 days; automated alerts at 75 days.",
            status=_status([("pass", 78), ("warning", 15), ("fail", 7)]),
            severity="high",
            evidence="Rotation policy enforced; 1 service account key at 88 days — rotation triggered today.",
            remediation="Confirm rotation of the 88-day key completes before audit submission.",
        ),
    ]

    # ------------------------------------------------------------------ Compliance
    compliance_checks = [
        SecurityCheck(
            check_id="COMP-001",
            category="compliance",
            name="SOC 2 Type II Readiness",
            description="Controls mapped to SOC 2 Trust Service Criteria; evidence collection automated.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="high",
            evidence="SOC 2 gap assessment complete (2026-01-20); 92% criteria met; audit scheduled Q2 2026.",
            remediation="Close 3 open gaps in CC6 (logical access) before audit window opens.",
        ),
        SecurityCheck(
            check_id="COMP-002",
            category="compliance",
            name="FedRAMP Control Mapping",
            description="NIST SP 800-53 Rev 5 controls mapped and implemented for FedRAMP Moderate baseline.",
            status=_status([("pass", 75), ("warning", 18), ("fail", 7)]),
            severity="critical",
            evidence="System Security Plan (SSP) v1.2 covers 325/325 required controls. POA&M has 8 open items.",
            remediation="Resolve 8 POA&M items — 3 are critical path for FedRAMP authorization.",
        ),
        SecurityCheck(
            check_id="COMP-003",
            category="compliance",
            name="GDPR Scope Assessment",
            description="Data residency is US-only; no EU data subjects processed — GDPR not applicable.",
            status="na",
            severity="medium",
            evidence="Legal review (2026-01-10) confirmed: service is US-only, no EU PII processed.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="COMP-004",
            category="compliance",
            name="Data Minimization Policy",
            description="Formal data minimization policy documented and enforced in data collection SDK.",
            status=_status([("pass", 82), ("warning", 13), ("fail", 5)]),
            severity="medium",
            evidence="Policy v1.3 published 2025-11-01; SDK data collection manifest reviewed and trimmed.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="COMP-005",
            category="compliance",
            name="Vulnerability Disclosure Policy",
            description="Published responsible disclosure policy with 90-day remedy SLA.",
            status=_status([("pass", 85), ("warning", 12), ("fail", 3)]),
            severity="medium",
            evidence="Policy published at security.oci-robot-cloud.oracle.com; HackerOne program active.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="COMP-006",
            category="compliance",
            name="Third-Party Dependency Scanning",
            description="All Python/container dependencies scanned weekly for CVEs; critical CVEs patched within 7 days.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="high",
            evidence="Trivy and pip-audit integrated in CI; 0 critical CVEs open as of 2026-03-28.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="COMP-007",
            category="compliance",
            name="Penetration Testing",
            description="Annual third-party penetration test; findings remediated before enterprise sales.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="high",
            evidence="Pentest by NCC Group completed 2026-02-15; 1 medium finding (NET-006 egress) open.",
            remediation="Close NET-006 egress finding prior to gov-cloud sales motion.",
        ),
    ]

    # ------------------------------------------------------------------ Incident Response
    ir_checks = [
        SecurityCheck(
            check_id="IR-001",
            category="incident_response",
            name="Incident Runbooks Documented",
            description="Runbooks exist for top-10 security incident scenarios; reviewed quarterly.",
            status=_status([("pass", 85), ("warning", 12), ("fail", 3)]),
            severity="high",
            evidence="10 runbooks in Confluence space /OCI-Robot-Cloud/IR; last reviewed 2025-12-01.",
            remediation="Schedule Q1 2026 runbook review — currently 7 weeks overdue.",
        ),
        SecurityCheck(
            check_id="IR-002",
            category="incident_response",
            name="RTO < 4 Hours",
            description="Recovery Time Objective for critical service outage tested and verified under 4 hours.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="critical",
            evidence="DR drill (2026-01-22): full restore in 2h 47m. Meets RTO target of 4h.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="IR-003",
            category="incident_response",
            name="Backup Integrity Verified",
            description="Weekly automated restore tests verify backup integrity for all critical data stores.",
            status=_status([("pass", 85), ("warning", 12), ("fail", 3)]),
            severity="high",
            evidence="Restore test logs: 4/4 weekly restores succeeded in past month; checksums verified.",
            remediation=None,
        ),
        SecurityCheck(
            check_id="IR-004",
            category="incident_response",
            name="Security Incident Notification SLA",
            description="Critical security incidents notify customers within 72 hours per contractual SLA.",
            status=_status([("pass", 82), ("warning", 13), ("fail", 5)]),
            severity="critical",
            evidence="No critical incidents in past 6 months. Notification workflow tested in tabletop (2026-01-10).",
            remediation=None,
        ),
        SecurityCheck(
            check_id="IR-005",
            category="incident_response",
            name="SIEM Integration",
            description="Security events from all components forwarded to centralized SIEM for correlation.",
            status=_status([("pass", 78), ("warning", 17), ("fail", 5)]),
            severity="high",
            evidence="OCI Logging Analytics SIEM integration active; alert rules for brute-force, privilege escalation.",
            remediation="Add log source for data collection API (port 8003) — currently not forwarded.",
        ),
        SecurityCheck(
            check_id="IR-006",
            category="incident_response",
            name="Post-Incident Reviews",
            description="All P1/P2 incidents trigger a post-mortem with root cause and action items.",
            status=_status([("pass", 80), ("warning", 15), ("fail", 5)]),
            severity="medium",
            evidence="2 P2 incidents in past 6 months; both have closed post-mortems with action items tracked.",
            remediation=None,
        ),
    ]

    checks.extend(api_checks)
    checks.extend(data_checks)
    checks.extend(network_checks)
    checks.extend(access_checks)
    checks.extend(compliance_checks)
    checks.extend(ir_checks)

    # Post-process: clear remediation on passing checks, ensure it exists on fail/warning
    generic_remediations = {
        "critical": "Escalate to security team immediately and open a P1 incident.",
        "high": "Create a remediation ticket with priority High; resolve within 30 days.",
        "medium": "Schedule for next sprint; document compensating control if delayed.",
        "low": "Track in security backlog; address in next quarterly review.",
    }
    for c in checks:
        if c.status == "pass":
            c.remediation = None
        elif c.status in ("fail", "warning") and not c.remediation:
            c.remediation = generic_remediations[c.severity]

    return checks


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_score(checks: List[SecurityCheck]):
    """Return overall score (0-100), grade, and per-category scores."""
    max_points = 0
    earned_points = 0
    cat_scores = {}

    for cat in CATEGORIES:
        cat_checks = [c for c in checks if c.category == cat and c.status != "na"]
        cat_max = sum(SEVERITY_WEIGHTS[c.severity] for c in cat_checks)
        cat_earned = 0
        for c in cat_checks:
            if c.status == "pass":
                cat_earned += SEVERITY_WEIGHTS[c.severity]
            elif c.status == "fail":
                cat_earned += SEVERITY_FAIL_PENALTIES[c.severity]
            # warning contributes 50% of pass points
            elif c.status == "warning":
                cat_earned += SEVERITY_WEIGHTS[c.severity] * 0.5
        cat_pct = max(0, min(100, round(100 * cat_earned / cat_max))) if cat_max > 0 else 100
        cat_scores[cat] = cat_pct
        max_points += cat_max
        earned_points += cat_earned

    overall = max(0, min(100, round(100 * earned_points / max_points))) if max_points > 0 else 100

    if overall >= 90:
        grade = "A"
    elif overall >= 75:
        grade = "B"
    elif overall >= 60:
        grade = "C"
    else:
        grade = "F"

    return overall, grade, cat_scores


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _radar_svg(cat_scores: dict, size: int = 300) -> str:
    """Generate a 6-axis radar chart SVG."""
    cx, cy, r = size // 2, size // 2, size // 2 - 40
    axes = CATEGORIES
    n = len(axes)
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def polar(angle, radius):
        x = cx + radius * math.cos(angle)
        y = cy - radius * math.sin(angle)
        return x, y

    lines = []
    # Background grid rings
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{polar(a, r * frac)[0]:.1f},{polar(a, r * frac)[1]:.1f}" for a in angles)
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>')

    # Axis spokes
    for a in angles:
        x, y = polar(a, r)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')

    # Data polygon
    data_pts = []
    for i, cat in enumerate(axes):
        frac = cat_scores.get(cat, 0) / 100.0
        x, y = polar(angles[i], r * frac)
        data_pts.append(f"{x:.1f},{y:.1f}")
    pts_str = " ".join(data_pts)
    lines.append(f'<polygon points="{pts_str}" fill="#C74634" fill-opacity="0.3" stroke="#C74634" stroke-width="2"/>')

    # Axis labels
    for i, cat in enumerate(axes):
        x, y = polar(angles[i], r + 20)
        label = CATEGORY_LABELS[cat].replace(" ", "\n")
        anchor = "middle"
        if x < cx - 5:
            anchor = "end"
        elif x > cx + 5:
            anchor = "start"
        score = cat_scores.get(cat, 0)
        lines.append(
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'fill="#94a3b8" font-size="9" font-family="monospace">'
            f'{CATEGORY_LABELS[cat]} {score}%</text>'
        )

    svg = (
        f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(lines)
        + "</svg>"
    )
    return svg


def _severity_bar_svg(checks: List[SecurityCheck], width: int = 560, height: int = 120) -> str:
    severities = ["critical", "high", "medium", "low"]
    colors_pass = {"critical": "#22c55e", "high": "#4ade80", "medium": "#86efac", "low": "#bbf7d0"}
    colors_fail = {"critical": "#ef4444", "high": "#f97316", "medium": "#fbbf24", "low": "#a3a3a3"}
    colors_warn = {"critical": "#f59e0b", "high": "#fcd34d", "medium": "#fde68a", "low": "#fef3c7"}

    bar_h = 20
    gap = 6
    label_w = 70
    bar_w = width - label_w - 20

    lines = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']

    for row, sev in enumerate(severities):
        sev_checks = [c for c in checks if c.severity == sev and c.status != "na"]
        total = len(sev_checks) or 1
        pass_n = sum(1 for c in sev_checks if c.status == "pass")
        warn_n = sum(1 for c in sev_checks if c.status == "warning")
        fail_n = sum(1 for c in sev_checks if c.status == "fail")
        y = row * (bar_h + gap) + 10

        lines.append(
            f'<text x="0" y="{y + bar_h - 5}" fill="#94a3b8" font-size="11" '
            f'font-family="monospace" text-anchor="start">{sev.upper()}</text>'
        )

        x = label_w
        for count, color in [(pass_n, colors_pass[sev]), (warn_n, colors_warn[sev]), (fail_n, colors_fail[sev])]:
            w = round(bar_w * count / total)
            if w > 0:
                lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" fill="{color}" rx="2"/>')
                if w > 18:
                    lines.append(
                        f'<text x="{x + w // 2}" y="{y + bar_h - 5}" text-anchor="middle" '
                        f'fill="#1e293b" font-size="10" font-family="monospace">{count}</text>'
                    )
            x += w

    # Legend
    ly = height - 14
    for i, (label, color) in enumerate(
        [("Pass", "#22c55e"), ("Warning", "#fbbf24"), ("Fail", "#ef4444")]
    ):
        lx = label_w + i * 110
        lines.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="{ly + 10}" fill="#94a3b8" font-size="11" font-family="monospace">{label}</text>')

    lines.append("</svg>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _status_badge(status: str) -> str:
    if status == "pass":
        return '<span style="color:#22c55e;font-weight:bold;">&#x2713; PASS</span>'
    elif status == "fail":
        return '<span style="color:#ef4444;font-weight:bold;">&#x2717; FAIL</span>'
    elif status == "warning":
        return '<span style="color:#f59e0b;font-weight:bold;">&#x26A0; WARN</span>'
    else:
        return '<span style="color:#64748b;">N/A</span>'


def _severity_chip(sev: str) -> str:
    colors = {"critical": "#ef4444", "high": "#f97316", "medium": "#fbbf24", "low": "#94a3b8"}
    color = colors.get(sev, "#94a3b8")
    return (
        f'<span style="background:{color};color:#1e293b;border-radius:4px;'
        f'padding:1px 6px;font-size:11px;font-weight:bold;">{sev.upper()}</span>'
    )


def generate_html_report(checks: List[SecurityCheck], score: int, grade: str, cat_scores: dict) -> str:
    today = date.today().isoformat()

    critical_fails = sum(1 for c in checks if c.severity == "critical" and c.status == "fail")
    total_checks = len(checks)

    grade_color = {"A": "#22c55e", "B": "#4ade80", "C": "#fbbf24", "F": "#ef4444"}.get(grade, "#94a3b8")

    if grade in ("A", "B") and critical_fails == 0:
        exec_summary = (
            "This deployment is <strong style='color:#22c55e;'>SUITABLE FOR ENTERPRISE DEPLOYMENT</strong>. "
            "All critical controls are passing and no blocker findings exist. "
            "Proceed with enterprise and government cloud sales engagements."
        )
    else:
        items = []
        if critical_fails > 0:
            items.append(f"{critical_fails} critical control(s) failing")
        if grade == "F":
            items.append("overall score below passing threshold")
        exec_summary = (
            "This deployment requires <strong style='color:#ef4444;'>REMEDIATION BEFORE ENTERPRISE DEPLOYMENT</strong>. "
            f"Identified issues: {'; '.join(items)}. "
            "Review the failing checks below and complete remediation before customer-facing security audits."
        )

    radar_svg = _radar_svg(cat_scores)
    bar_svg = _severity_bar_svg(checks)

    # Build check rows grouped by category
    rows_html = []
    for cat in CATEGORIES:
        cat_label = CATEGORY_LABELS[cat]
        cat_checks = [c for c in checks if c.category == cat]
        rows_html.append(
            f'<tr><td colspan="5" style="background:#0f172a;color:#C74634;'
            f'font-weight:bold;padding:8px 12px;font-size:13px;">'
            f'{cat_label} ({len(cat_checks)} checks)</td></tr>'
        )
        for c in cat_checks:
            remediation_td = (
                f'<small style="color:#fbbf24;">{c.remediation}</small>'
                if c.remediation
                else '<small style="color:#475569;">—</small>'
            )
            rows_html.append(
                f"<tr>"
                f'<td style="color:#94a3b8;font-size:11px;white-space:nowrap;">{c.check_id}</td>'
                f'<td style="color:#e2e8f0;">{c.name}</td>'
                f"<td>{_status_badge(c.status)}</td>"
                f"<td>{_severity_chip(c.severity)}</td>"
                f'<td><small style="color:#94a3b8;">{c.evidence}</small><br>{remediation_td}</td>'
                f"</tr>"
            )

    rows = "\n".join(rows_html)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCI Robot Cloud — Security Audit Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; }}
  .header {{ background: #0f172a; padding: 28px 40px; border-bottom: 3px solid #C74634; }}
  .header h1 {{ color: #C74634; font-size: 24px; letter-spacing: 1px; }}
  .header p {{ color: #94a3b8; margin-top: 4px; font-size: 13px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 40px; }}
  .kpi-row {{ display: flex; gap: 20px; margin-bottom: 32px; flex-wrap: wrap; }}
  .kpi {{ flex: 1; min-width: 200px; background: #0f172a; border: 1px solid #334155;
           border-radius: 8px; padding: 20px 24px; }}
  .kpi .value {{ font-size: 36px; font-weight: bold; color: #C74634; }}
  .kpi .label {{ color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }}
  .charts-row {{ display: flex; gap: 24px; margin-bottom: 32px; flex-wrap: wrap; align-items: flex-start; }}
  .chart-box {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 20px 24px; }}
  .chart-box h3 {{ color: #C74634; font-size: 14px; margin-bottom: 12px; }}
  .exec-box {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px;
               padding: 20px 24px; margin-bottom: 32px; line-height: 1.6; }}
  .exec-box h3 {{ color: #C74634; font-size: 14px; margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; background: #0f172a; border-radius: 8px; overflow: hidden; }}
  th {{ background: #1e293b; color: #94a3b8; font-size: 12px; text-transform: uppercase;
        letter-spacing: 1px; padding: 10px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; vertical-align: top; }}
  tr:hover td {{ background: #1a2840; }}
  .section-title {{ color: #C74634; font-size: 18px; margin-bottom: 16px; font-weight: bold; }}
  .footer {{ color: #475569; font-size: 11px; text-align: center; margin-top: 40px; padding-bottom: 24px; }}
</style>
</head>
<body>
<div class="header">
  <h1>OCI Robot Cloud &mdash; Enterprise Security Audit Report</h1>
  <p>Comprehensive security assessment covering API security, data handling, network, access control, compliance, and incident response</p>
</div>
<div class="container">

  <!-- KPI Cards -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="value" style="color:{grade_color};">{grade}</div>
      <div class="label">Overall Grade ({score}/100)</div>
    </div>
    <div class="kpi">
      <div class="value">{total_checks}</div>
      <div class="label">Total Checks</div>
    </div>
    <div class="kpi">
      <div class="value" style="color:{'#ef4444' if critical_fails > 0 else '#22c55e'};">{critical_fails}</div>
      <div class="label">Critical Issues</div>
    </div>
    <div class="kpi">
      <div class="value" style="font-size:22px;">{today}</div>
      <div class="label">Audit Date</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-box">
      <h3>Category Radar</h3>
      {radar_svg}
    </div>
    <div class="chart-box" style="flex:1;min-width:320px;">
      <h3>Severity Breakdown</h3>
      {bar_svg}
      <p style="color:#475569;font-size:11px;margin-top:8px;">
        Bar width proportional to checks per severity tier.
      </p>
    </div>
  </div>

  <!-- Executive Summary -->
  <div class="exec-box">
    <h3>Executive Summary</h3>
    <p>{exec_summary}</p>
  </div>

  <!-- Check Table -->
  <div class="section-title">Security Checks Detail</div>
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Check</th>
        <th>Status</th>
        <th>Severity</th>
        <th>Evidence / Remediation</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <div class="footer">
    OCI Robot Cloud &mdash; Security Audit Report &mdash; Generated {today} &mdash; CONFIDENTIAL
  </div>
</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Security Audit Report Generator")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock data (default: true)")
    parser.add_argument("--output", default="/tmp/security_audit_report.html", help="Output HTML file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data generation")
    args = parser.parse_args()

    print(f"[security_audit] Generating security checks (seed={args.seed})...")
    checks = generate_security_checks(seed=args.seed)

    score, grade, cat_scores = compute_score(checks)

    pass_n = sum(1 for c in checks if c.status == "pass")
    fail_n = sum(1 for c in checks if c.status == "fail")
    warn_n = sum(1 for c in checks if c.status == "warning")
    na_n = sum(1 for c in checks if c.status == "na")

    print(f"[security_audit] Results: {len(checks)} checks | Pass={pass_n} Warn={warn_n} Fail={fail_n} N/A={na_n}")
    print(f"[security_audit] Overall score: {score}/100 (Grade {grade})")
    for cat in CATEGORIES:
        print(f"  {CATEGORY_LABELS[cat]:25s}: {cat_scores[cat]:3d}%")

    html = generate_html_report(checks, score, grade, cat_scores)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[security_audit] Report written to: {args.output}")
    critical_fails = sum(1 for c in checks if c.severity == "critical" and c.status == "fail")
    if critical_fails > 0:
        print(f"[security_audit] WARNING: {critical_fails} critical checks failing — remediation required before enterprise sales.")
    else:
        print("[security_audit] No critical failures — suitable for enterprise deployment.")


if __name__ == "__main__":
    main()
