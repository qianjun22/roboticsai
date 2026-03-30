"""
data_privacy_checker.py — Oracle OCI Robot Cloud
=================================================
Validates that design partner episode data meets Oracle's data privacy and
compliance requirements before the data enters the training pipeline.

Required for government cloud (FedRAMP/IL4) and manufacturing customers who
need documented evidence of data provenance, PII scrubbing, and license
compatibility before model training can proceed.

Usage
-----
# Run against mock data (50 episodes, 2 injected edge cases) and save HTML report:
    python src/eval/data_privacy_checker.py --mock --n-episodes 50 --output /tmp/privacy_report.html

# Run against a real episode directory:
    python src/eval/data_privacy_checker.py --episode-dir /data/partner_episodes --output /tmp/privacy_report.html

# JSON output instead of HTML:
    python src/eval/data_privacy_checker.py --mock --output /tmp/privacy_report.json

Compliance Checks
-----------------
1. PII scan          — No names, emails, or IP addresses in episode metadata
2. Face detection    — Camera images must not contain face-like regions (histogram proxy)
3. Joint bounds      — All joint state values within published hardware limits
4. Data provenance   — Episodes have valid source; real-robot requires partner attestation
5. License compat    — Dataset license allows commercial use + redistribution
6. US-origin data    — No non-US IP addresses in collection metadata
7. Data minimization — Only required fields present (obs, action, timestamp)
8. Retention policy  — No episode timestamps older than 2 years

Risk Score
----------
Each failed check contributes points toward a 0–10 risk score.
Training is BLOCKED when risk >= 7.

Exit Codes
----------
0  — COMPLIANT (risk < 7, training allowed)
1  — NON-COMPLIANT (risk >= 7, training blocked)
2  — Internal error
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Published hardware joint limits (radians or metres, depending on joint type)
JOINT_LIMITS: dict[str, tuple[float, float]] = {
    "joint_0": (-3.14159, 3.14159),   # base rotation
    "joint_1": (-1.5708, 1.5708),     # shoulder
    "joint_2": (-2.6180, 2.6180),     # elbow
    "joint_3": (-3.14159, 3.14159),   # wrist roll
    "joint_4": (-1.5708, 1.5708),     # wrist pitch
    "joint_5": (-3.14159, 3.14159),   # wrist yaw
    "gripper":  (0.0, 0.08),          # gripper opening (metres)
}

REQUIRED_FIELDS = {"obs", "action", "timestamp"}

ALLOWED_LICENSES = {
    "cc-by-4.0", "cc-by-3.0", "cc-by-2.0",
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause",
    "openrail", "proprietary-oracle",  # Oracle internal
}

RETENTION_MAX_DAYS = 730  # 2 years

# Risk weights per check (sum over failing checks = raw score, then normalised to 0-10)
CHECK_WEIGHTS: dict[str, float] = {
    "pii_scan":        3.0,
    "face_detection":  2.5,
    "joint_bounds":    1.5,
    "data_provenance": 2.0,
    "license_compat":  2.5,
    "us_origin":       2.0,
    "data_minimization": 1.0,
    "retention_policy": 1.5,
}
_MAX_RAW_SCORE = sum(CHECK_WEIGHTS.values())  # 16.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    check_id: str
    label: str
    status: str          # "PASS" | "WARN" | "FAIL"
    detail: str
    remediation: str = ""
    affected_episodes: list[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    generated_at: str
    n_episodes: int
    checks: list[CheckResult]
    risk_score: float       # 0.0 – 10.0
    overall: str            # "COMPLIANT" | "NON-COMPLIANT"
    training_blocked: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "n_episodes": self.n_episodes,
            "risk_score": round(self.risk_score, 2),
            "overall": self.overall,
            "training_blocked": self.training_blocked,
            "checks": [
                {
                    "check_id": c.check_id,
                    "label": c.label,
                    "status": c.status,
                    "detail": c.detail,
                    "remediation": c.remediation,
                    "affected_episodes": c.affected_episodes,
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Mock episode generator
# ---------------------------------------------------------------------------

def _fake_image_bytes(width: int = 64, height: int = 64, face_like: bool = False) -> bytes:
    """
    Generate a minimal raw RGB byte buffer that mimics a camera image.
    If face_like=True, embed a skin-tone dominant region (high R, medium G, low B)
    so the histogram proxy check can flag it.

    The buffer is encoded as:  4-byte magic + 4-byte width + 4-byte height + RGB bytes.
    No external image libraries required.
    """
    magic = b"RIMG"
    header = magic + width.to_bytes(4, "little") + height.to_bytes(4, "little")
    if face_like:
        # Skin-tone: R~200, G~150, B~100 dominant
        pixels = bytes([200, 150, 100] * (width * height))
    else:
        # Random scene colours
        rng = random.Random(width * height)
        pixels = bytes([rng.randint(30, 220) for _ in range(width * height * 3)])
    return header + pixels


def generate_mock_episodes(n: int = 50, seed: int = 42) -> list[dict[str, Any]]:
    """
    Return a list of episode dicts.  Two edge cases are always injected:
      - Episode index 7  : PII in metadata (email address)
      - Episode index 23 : Out-of-bounds joint state (joint_2 > limit)
    """
    rng = random.Random(seed)
    now_ts = datetime.now(timezone.utc).timestamp()
    episodes: list[dict[str, Any]] = []

    for i in range(n):
        ts = now_ts - rng.uniform(0, 400 * 86400)  # up to ~13 months ago

        meta: dict[str, Any] = {
            "episode_id": f"ep_{i:04d}",
            "source": rng.choice(["simulator", "simulator", "simulator", "real-robot"]),
            "license": rng.choice(["cc-by-4.0", "mit", "apache-2.0"]),
            "collection_ip": f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}",
            "partner_attestation": True,
            "extra_fields": [],
        }

        # Build joint states: 10 timesteps per episode
        joint_states: list[dict[str, float]] = []
        for _ in range(10):
            js: dict[str, float] = {}
            for jname, (lo, hi) in JOINT_LIMITS.items():
                js[jname] = rng.uniform(lo * 0.9, hi * 0.9)
            joint_states.append(js)

        episode: dict[str, Any] = {
            "obs": {
                "camera_0": _fake_image_bytes(64, 64, face_like=False),
                "joint_states": joint_states,
            },
            "action": [[rng.uniform(-1, 1) for _ in range(7)] for _ in range(10)],
            "timestamp": ts,
            "metadata": meta,
        }

        # ---- Inject edge case 1: PII in metadata ----
        if i == 7:
            meta["operator_email"] = "john.doe@acme-robotics.com"

        # ---- Inject edge case 2: out-of-bounds joint state ----
        if i == 23:
            joint_states[3]["joint_2"] = 5.5  # limit is ±2.618

        episodes.append(episode)

    return episodes


# ---------------------------------------------------------------------------
# Image face-detection proxy (no external deps)
# ---------------------------------------------------------------------------

def _decode_image_to_rgb(raw: bytes) -> tuple[int, int, list[int]] | None:
    """
    Decode our custom RIMG format → (width, height, flat_rgb_list).
    Returns None for unknown formats.
    """
    if len(raw) < 12:
        return None
    if raw[:4] != b"RIMG":
        return None
    width = int.from_bytes(raw[4:8], "little")
    height = int.from_bytes(raw[8:12], "little")
    pixels = list(raw[12:12 + width * height * 3])
    return width, height, pixels


def _has_face_like_region(raw: bytes, threshold: float = 0.25) -> bool:
    """
    Proxy face detection via colour histogram.

    Rationale: human skin tones occupy a narrow band in RGB space
    (R > 160, G in [90,180], B < 140, and R > G > B).  If more than
    `threshold` fraction of pixels satisfy these criteria, we flag the
    image as potentially containing a face.

    This is intentionally conservative (high recall, lower precision) —
    a separate manual review step handles false positives.
    """
    decoded = _decode_image_to_rgb(raw)
    if decoded is None:
        return False
    _, _, pixels = decoded
    n_px = len(pixels) // 3
    if n_px == 0:
        return False
    skin_count = 0
    for p in range(n_px):
        r, g, b = pixels[p * 3], pixels[p * 3 + 1], pixels[p * 3 + 2]
        if r > 160 and 90 <= g <= 180 and b < 140 and r > g > b:
            skin_count += 1
    return (skin_count / n_px) >= threshold


# ---------------------------------------------------------------------------
# Individual compliance checks
# ---------------------------------------------------------------------------

PII_PATTERNS = [
    ("email",        re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    ("proper_name",  re.compile(r"\b(?:[A-Z][a-z]+\s+){1,2}[A-Z][a-z]+\b")),
    ("ssn",          re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone",        re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")),
]

# Fields whose values are exempt from PII scanning (handled by dedicated checks)
_PII_EXEMPT_KEYS = {"collection_ip", "episode_id", "source", "license",
                    "partner_attestation", "extra_fields"}


def _scrub_exempt_fields(meta: dict) -> dict:
    """Return a copy of meta with exempt keys removed before PII scanning."""
    return {k: v for k, v in meta.items() if k not in _PII_EXEMPT_KEYS}


def check_pii_scan(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        scannable_meta = _scrub_exempt_fields(ep.get("metadata", {}))
        meta_str = json.dumps(scannable_meta)
        for label, pat in PII_PATTERNS:
            if pat.search(meta_str):
                violations.append(f"{ep_id} ({label})")
                break
    if not violations:
        return CheckResult(
            check_id="pii_scan", label="PII Scan",
            status="PASS",
            detail="No personally identifiable information detected in episode metadata.",
        )
    return CheckResult(
        check_id="pii_scan", label="PII Scan",
        status="FAIL",
        detail=f"{len(violations)} episode(s) contain PII in metadata.",
        remediation=(
            "Strip all personally identifiable fields (emails, names, phone numbers, SSNs) "
            "from episode metadata before ingestion. Use the anonymization script: "
            "`python src/data/anonymize_metadata.py --episode-dir <path>`"
        ),
        affected_episodes=violations,
    )


def check_face_detection(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        obs = ep.get("obs", {})
        for key, val in obs.items():
            if isinstance(val, (bytes, bytearray)) and _has_face_like_region(bytes(val)):
                violations.append(f"{ep_id}/{key}")
    if not violations:
        return CheckResult(
            check_id="face_detection", label="Face Detection",
            status="PASS",
            detail="No face-like regions detected in camera images (colour histogram proxy).",
        )
    return CheckResult(
        check_id="face_detection", label="Face Detection",
        status="FAIL",
        detail=f"{len(violations)} image stream(s) may contain human faces.",
        remediation=(
            "Run face-blurring on all camera streams before submission: "
            "`python src/data/blur_faces.py --episode-dir <path>`. "
            "For GDPR/CCPA compliance, facial data requires explicit written consent."
        ),
        affected_episodes=violations,
    )


def check_joint_bounds(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        joint_states = ep.get("obs", {}).get("joint_states", [])
        for step_idx, js in enumerate(joint_states):
            for jname, (lo, hi) in JOINT_LIMITS.items():
                val = js.get(jname)
                if val is None:
                    continue
                if not (lo <= val <= hi):
                    violations.append(f"{ep_id}/step{step_idx}/{jname}={val:.4f}")
    if not violations:
        return CheckResult(
            check_id="joint_bounds", label="Joint State Bounds",
            status="PASS",
            detail=f"All joint states within published hardware limits across {len(episodes)} episodes.",
        )
    return CheckResult(
        check_id="joint_bounds", label="Joint State Bounds",
        status="FAIL",
        detail=f"{len(violations)} out-of-bounds joint state reading(s) detected.",
        remediation=(
            "Out-of-bounds values indicate sensor faults, data tampering, or a different "
            "robot model. Filter episodes with `python src/data/filter_bounds.py`. "
            "If intentional (wider-range arm), update JOINT_LIMITS in this checker."
        ),
        affected_episodes=violations[:20],  # cap display list
    )


def check_data_provenance(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    warn_episodes: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        meta = ep.get("metadata", {})
        source = meta.get("source", "")
        if source == "simulator":
            continue  # always pass
        elif source == "real-robot":
            if not meta.get("partner_attestation", False):
                violations.append(ep_id)
        else:
            warn_episodes.append(f"{ep_id} (source='{source}')")

    if violations:
        return CheckResult(
            check_id="data_provenance", label="Data Provenance",
            status="FAIL",
            detail=f"{len(violations)} real-robot episode(s) lack partner attestation.",
            remediation=(
                "Obtain a signed Partner Data Use Attestation form (DocuSign template "
                "OCI-ROB-DUA-001) for each real-robot collection session. "
                "Set `partner_attestation: true` in episode metadata once signed."
            ),
            affected_episodes=violations,
        )
    if warn_episodes:
        return CheckResult(
            check_id="data_provenance", label="Data Provenance",
            status="WARN",
            detail=f"{len(warn_episodes)} episode(s) have unrecognised source labels.",
            remediation=(
                "Set `source` to 'simulator' or 'real-robot' in episode metadata."
            ),
            affected_episodes=warn_episodes,
        )
    return CheckResult(
        check_id="data_provenance", label="Data Provenance",
        status="PASS",
        detail="All episodes have valid source; real-robot episodes have partner attestation.",
    )


def check_license_compat(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    seen_licenses: set[str] = set()
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        lic = str(ep.get("metadata", {}).get("license", "")).lower().strip()
        seen_licenses.add(lic)
        if lic not in ALLOWED_LICENSES:
            violations.append(f"{ep_id} (license='{lic}')")
    if not violations:
        return CheckResult(
            check_id="license_compat", label="License Compatibility",
            status="PASS",
            detail=f"All episodes carry commercially compatible licenses: {sorted(seen_licenses)}",
        )
    return CheckResult(
        check_id="license_compat", label="License Compatibility",
        status="FAIL",
        detail=f"{len(violations)} episode(s) have incompatible or unknown licenses.",
        remediation=(
            "Accepted commercial licenses: CC-BY-*, MIT, Apache-2.0, BSD-2/3, "
            "OpenRAIL, proprietary-oracle. Contact legal@oracle.com to assess "
            "other licenses. Episodes with non-commercial-only licenses (CC-NC) "
            "must be excluded from training datasets."
        ),
        affected_episodes=violations[:20],
    )


def _is_us_ip(ip_str: str) -> bool:
    """
    Approximate US-IP check: RFC-1918 private ranges are treated as US-origin
    (internal Oracle/lab networks). Public non-RFC-1918 IPs are flagged as
    potentially non-US origin (a real implementation would use a GeoIP database).
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False  # unparseable → flag
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return True
    # For public IPs, we treat 3.x.x.x / 52.x.x.x / 54.x.x.x as AWS US (common lab usage)
    first_octet = int(ip_str.split(".")[0])
    aws_us_ranges = {3, 18, 34, 35, 44, 52, 54}
    return first_octet in aws_us_ranges


def check_us_origin(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        ip = ep.get("metadata", {}).get("collection_ip", "")
        if ip and not _is_us_ip(ip):
            violations.append(f"{ep_id} (ip={ip})")
    if not violations:
        return CheckResult(
            check_id="us_origin", label="US-Origin Data",
            status="PASS",
            detail="All collection IPs resolve to US-origin or private/internal networks.",
        )
    return CheckResult(
        check_id="us_origin", label="US-Origin Data",
        status="FAIL",
        detail=f"{len(violations)} episode(s) have collection IPs that may be non-US origin.",
        remediation=(
            "Government cloud (OC2/OC3) and IL4 contracts require data collected within "
            "US jurisdiction. Verify with partner that data was collected on US soil. "
            "If collected abroad, a ITAR/EAR export control review is required before "
            "training. Contact export-control@oracle.com."
        ),
        affected_episodes=violations[:20],
    )


def check_data_minimization(episodes: list[dict]) -> CheckResult:
    violations: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        top_keys = set(ep.keys())
        extra = top_keys - REQUIRED_FIELDS - {"metadata"}
        meta_extra = set(ep.get("metadata", {}).get("extra_fields", []))
        if extra or meta_extra:
            violations.append(f"{ep_id} (extra_keys={sorted(extra | meta_extra)})")
    if not violations:
        return CheckResult(
            check_id="data_minimization", label="Data Minimization",
            status="PASS",
            detail=f"All episodes contain only required fields: {sorted(REQUIRED_FIELDS)}.",
        )
    return CheckResult(
        check_id="data_minimization", label="Data Minimization",
        status="WARN",
        detail=f"{len(violations)} episode(s) contain fields beyond the required set.",
        remediation=(
            "Remove unnecessary fields before ingestion to minimise data footprint "
            "per GDPR Article 5(1)(c) and Oracle DPA §3.2. "
            "Required fields are: obs, action, timestamp. "
            "Use `python src/data/minimize_fields.py --episode-dir <path>`."
        ),
        affected_episodes=violations[:20],
    )


def check_retention_policy(episodes: list[dict]) -> CheckResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_MAX_DAYS)
    cutoff_ts = cutoff.timestamp()
    violations: list[str] = []
    for ep in episodes:
        ep_id = ep.get("metadata", {}).get("episode_id", "unknown")
        ts = ep.get("timestamp")
        if ts is not None and ts < cutoff_ts:
            age_days = (datetime.now(timezone.utc).timestamp() - ts) / 86400
            violations.append(f"{ep_id} (age={age_days:.0f}d)")
    if not violations:
        return CheckResult(
            check_id="retention_policy", label="Retention Policy",
            status="PASS",
            detail=f"All episodes within 2-year retention window (cutoff: {cutoff.date()}).",
        )
    return CheckResult(
        check_id="retention_policy", label="Retention Policy",
        status="FAIL",
        detail=f"{len(violations)} episode(s) exceed the 2-year data retention limit.",
        remediation=(
            "Delete or archive episodes older than 2 years per Oracle Data Retention "
            "Policy ODP-2024-07. Run `python src/data/purge_expired.py --before "
            f"{cutoff.date()}` to remove expired data. Do not use expired data for training."
        ),
        affected_episodes=violations[:20],
    )


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

def compute_risk_score(checks: list[CheckResult]) -> float:
    """
    Sum the weights of all FAIL checks, scale to 0–10.
    WARN checks contribute half their weight.
    """
    raw = 0.0
    for c in checks:
        w = CHECK_WEIGHTS.get(c.check_id, 1.0)
        if c.status == "FAIL":
            raw += w
        elif c.status == "WARN":
            raw += w * 0.5
    return min(10.0, (raw / _MAX_RAW_SCORE) * 10.0)


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def run_all_checks(episodes: list[dict]) -> ComplianceReport:
    checks: list[CheckResult] = [
        check_pii_scan(episodes),
        check_face_detection(episodes),
        check_joint_bounds(episodes),
        check_data_provenance(episodes),
        check_license_compat(episodes),
        check_us_origin(episodes),
        check_data_minimization(episodes),
        check_retention_policy(episodes),
    ]
    risk = compute_risk_score(checks)
    blocked = risk >= 7.0
    overall = "NON-COMPLIANT" if blocked else "COMPLIANT"
    return ComplianceReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        n_episodes=len(episodes),
        checks=checks,
        risk_score=risk,
        overall=overall,
        training_blocked=blocked,
    )


# ---------------------------------------------------------------------------
# HTML report renderer (dark theme, no external deps)
# ---------------------------------------------------------------------------

_STATUS_COLOR = {
    "PASS": "#22c55e",   # green
    "WARN": "#f59e0b",   # amber
    "FAIL": "#ef4444",   # red
}

_BADGE_STYLE = {
    "COMPLIANT":     "background:#15803d;color:#dcfce7;",
    "NON-COMPLIANT": "background:#991b1b;color:#fee2e2;",
}


def _risk_bar_html(score: float) -> str:
    pct = score / 10.0 * 100
    if score < 4:
        color = "#22c55e"
    elif score < 7:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    return (
        f'<div style="background:#374151;border-radius:4px;height:18px;width:100%;">'
        f'<div style="width:{pct:.1f}%;background:{color};height:18px;border-radius:4px;'
        f'transition:width 0.3s;"></div></div>'
    )


def _check_rows_html(checks: list[CheckResult]) -> str:
    rows = []
    for c in checks:
        color = _STATUS_COLOR.get(c.status, "#9ca3af")
        badge = (
            f'<span style="background:{color};color:#000;border-radius:4px;'
            f'padding:2px 8px;font-size:12px;font-weight:700;">{c.status}</span>'
        )
        affected_html = ""
        if c.affected_episodes:
            items = "".join(
                f'<li style="font-family:monospace;font-size:12px;color:#d1d5db;">{e}</li>'
                for e in c.affected_episodes[:10]
            )
            more = f"<li style='color:#9ca3af;font-size:11px;'>…and {len(c.affected_episodes)-10} more</li>" if len(c.affected_episodes) > 10 else ""
            affected_html = f'<ul style="margin:6px 0 0 16px;padding:0;">{items}{more}</ul>'

        remediation_html = ""
        if c.remediation:
            remediation_html = (
                f'<div style="margin-top:8px;padding:8px 12px;background:#1f2937;'
                f'border-left:3px solid #f59e0b;border-radius:0 4px 4px 0;">'
                f'<span style="color:#f59e0b;font-size:11px;font-weight:700;">REMEDIATION</span>'
                f'<p style="color:#d1d5db;font-size:13px;margin:4px 0 0 0;">{c.remediation}</p>'
                f'</div>'
            )

        rows.append(
            f'<tr>'
            f'<td style="padding:14px 16px;vertical-align:top;white-space:nowrap;">'
            f'<span style="color:#e5e7eb;font-weight:600;font-size:14px;">{c.label}</span>'
            f'</td>'
            f'<td style="padding:14px 16px;vertical-align:top;">{badge}</td>'
            f'<td style="padding:14px 16px;color:#d1d5db;font-size:13px;vertical-align:top;">'
            f'{c.detail}{affected_html}{remediation_html}'
            f'</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def render_html_report(report: ComplianceReport) -> str:
    badge_style = _BADGE_STYLE.get(report.overall, "")
    blocked_banner = ""
    if report.training_blocked:
        blocked_banner = (
            '<div style="background:#7f1d1d;border:1px solid #ef4444;border-radius:6px;'
            'padding:12px 18px;margin-bottom:20px;color:#fca5a5;font-weight:600;font-size:14px;">'
            '&#128683; TRAINING BLOCKED — Risk score &ge;7. Resolve all FAIL checks before '
            'submitting data to the training pipeline.</div>'
        )

    pass_count = sum(1 for c in report.checks if c.status == "PASS")
    warn_count = sum(1 for c in report.checks if c.status == "WARN")
    fail_count = sum(1 for c in report.checks if c.status == "FAIL")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — Data Privacy Compliance Report</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#111827;color:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:32px;}}
  h1{{font-size:22px;font-weight:700;color:#f9fafb;}}
  h2{{font-size:15px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px;}}
  .card{{background:#1f2937;border-radius:8px;padding:20px 24px;margin-bottom:20px;}}
  table{{width:100%;border-collapse:collapse;}}
  tr:not(:last-child){{border-bottom:1px solid #374151;}}
  td{{vertical-align:top;}}
  .meta-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;}}
  .meta-item label{{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;}}
  .meta-item p{{font-size:18px;font-weight:700;color:#f9fafb;margin-top:4px;}}
</style>
</head>
<body>

<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
  <div>
    <p style="color:#6b7280;font-size:13px;margin-bottom:4px;">Oracle OCI Robot Cloud</p>
    <h1>Data Privacy &amp; Compliance Report</h1>
    <p style="color:#6b7280;font-size:12px;margin-top:4px;">Generated: {report.generated_at}</p>
  </div>
  <span style="{badge_style}padding:8px 20px;border-radius:6px;font-size:18px;font-weight:800;letter-spacing:.03em;">
    {report.overall}
  </span>
</div>

{blocked_banner}

<div class="card">
  <h2>Summary</h2>
  <div class="meta-grid">
    <div class="meta-item"><label>Episodes Scanned</label><p>{report.n_episodes}</p></div>
    <div class="meta-item"><label>Checks Run</label><p>{len(report.checks)}</p></div>
    <div class="meta-item"><label style="color:#22c55e;">Passed</label><p style="color:#22c55e;">{pass_count}</p></div>
    <div class="meta-item"><label style="color:#f59e0b;">Warnings</label><p style="color:#f59e0b;">{warn_count}</p></div>
    <div class="meta-item"><label style="color:#ef4444;">Failed</label><p style="color:#ef4444;">{fail_count}</p></div>
    <div class="meta-item"><label>Training Blocked</label><p style="color:{'#ef4444' if report.training_blocked else '#22c55e'}">{'YES' if report.training_blocked else 'NO'}</p></div>
  </div>
  <div style="margin-top:16px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
      <span style="font-size:13px;color:#9ca3af;">Risk Score</span>
      <span style="font-size:16px;font-weight:700;color:#f9fafb;">{report.risk_score:.1f} / 10.0</span>
    </div>
    {_risk_bar_html(report.risk_score)}
    <p style="font-size:11px;color:#6b7280;margin-top:4px;">
      0–3 Low &nbsp;|&nbsp; 4–6 Medium &nbsp;|&nbsp; 7–10 High (training blocked at &ge;7)
    </p>
  </div>
</div>

<div class="card">
  <h2>Check Details</h2>
  <table>
    <thead>
      <tr style="border-bottom:2px solid #374151;">
        <th style="text-align:left;padding:10px 16px;color:#6b7280;font-size:12px;font-weight:600;text-transform:uppercase;white-space:nowrap;">Check</th>
        <th style="text-align:left;padding:10px 16px;color:#6b7280;font-size:12px;font-weight:600;text-transform:uppercase;">Status</th>
        <th style="text-align:left;padding:10px 16px;color:#6b7280;font-size:12px;font-weight:600;text-transform:uppercase;">Details &amp; Remediation</th>
      </tr>
    </thead>
    <tbody>
      {_check_rows_html(report.checks)}
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Check Weights (Risk Contribution)</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;">
    {''.join(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:8px 12px;background:#111827;border-radius:4px;">'
        f'<span style="font-size:13px;color:#d1d5db;">{cid.replace("_"," ").title()}</span>'
        f'<span style="font-size:13px;font-weight:600;color:#9ca3af;">{w:.1f}</span>'
        f'</div>'
        for cid, w in CHECK_WEIGHTS.items()
    )}
  </div>
  <p style="font-size:11px;color:#6b7280;margin-top:10px;">
    Raw weight sum = {_MAX_RAW_SCORE:.1f}. Risk score = (sum of failing weights / {_MAX_RAW_SCORE:.1f}) &times; 10.
    WARNs count at 50%.
  </p>
</div>

<div style="margin-top:24px;text-align:center;color:#374151;font-size:11px;">
  Oracle Confidential &mdash; OCI Robot Cloud &mdash; Data Privacy Compliance Checker v1.0
</div>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Load episodes from a directory (real data path)
# ---------------------------------------------------------------------------

def load_episodes_from_dir(episode_dir: str) -> list[dict]:
    """
    Load episodes from a directory.  Each episode is expected to be a JSON
    file named `ep_NNNN.json` or similar.  Binary image fields stored as
    base64 strings are decoded back to bytes automatically.
    """
    import glob as _glob

    pattern = os.path.join(episode_dir, "*.json")
    paths = sorted(_glob.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No *.json episode files found in {episode_dir!r}")

    episodes = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            ep = json.load(fh)
        # Decode base64 image fields
        obs = ep.get("obs", {})
        for k, v in obs.items():
            if isinstance(v, str):
                try:
                    obs[k] = base64.b64decode(v)
                except Exception:
                    pass
        episodes.append(ep)
    return episodes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Oracle OCI Robot Cloud — Data Privacy & Compliance Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--mock", action="store_true",
        help="Generate synthetic mock episodes with injected edge cases.",
    )
    source.add_argument(
        "--episode-dir", metavar="PATH",
        help="Directory containing real episode JSON files.",
    )
    parser.add_argument(
        "--n-episodes", type=int, default=50,
        help="Number of mock episodes to generate (default: 50, only with --mock).",
    )
    parser.add_argument(
        "--output", metavar="PATH", default="/tmp/privacy_report.html",
        help="Output file path (.html or .json, default: /tmp/privacy_report.html).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for mock data generation (default: 42).",
    )
    args = parser.parse_args()

    # Load episodes
    print("Loading episodes…", flush=True)
    t0 = time.perf_counter()
    if args.mock:
        episodes = generate_mock_episodes(n=args.n_episodes, seed=args.seed)
        print(f"  Generated {len(episodes)} mock episodes (seed={args.seed}).")
    else:
        try:
            episodes = load_episodes_from_dir(args.episode_dir)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"  Loaded {len(episodes)} episodes from {args.episode_dir!r}.")

    # Run checks
    print("Running compliance checks…", flush=True)
    report = run_all_checks(episodes)
    elapsed = time.perf_counter() - t0

    # Print summary to stdout
    print()
    print(f"  {'Check':<30}  {'Status':<6}  {'Affected'}")
    print(f"  {'-'*30}  {'-'*6}  {'-'*20}")
    for c in report.checks:
        aff = f"{len(c.affected_episodes)} item(s)" if c.affected_episodes else "—"
        print(f"  {c.label:<30}  {c.status:<6}  {aff}")
    print()
    print(f"  Risk score : {report.risk_score:.1f} / 10.0")
    print(f"  Overall    : {report.overall}")
    if report.training_blocked:
        print("  *** TRAINING BLOCKED (risk >= 7) ***")
    print(f"  Elapsed    : {elapsed:.2f}s")
    print()

    # Write output
    out_path = args.output
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if out_path.endswith(".json"):
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2)
    else:
        html = render_html_report(report)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html)

    print(f"Report saved → {out_path}")

    return 1 if report.training_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
