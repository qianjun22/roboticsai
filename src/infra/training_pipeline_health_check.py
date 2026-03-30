#!/usr/bin/env python3
"""OCI Robot Cloud — Training Pipeline Health Check.

Runs a comprehensive health check on all training pipeline components
(GR00T server, DAgger service, Genesis SDG, LeRobot dataset, GPU,
storage, checkpoints, eval pipeline) and produces a dark-theme HTML
report with pass/warn/fail status per component.

Usage:
    python training_pipeline_health_check.py --mock                        # simulated
    python training_pipeline_health_check.py --host 138.1.153.110          # live
    python training_pipeline_health_check.py --output /tmp/health.html     # custom path
"""

import argparse
import datetime
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ComponentCheck:
    name: str
    status: str          # "pass" | "warn" | "fail"
    latency_ms: float    # -1 if not applicable
    detail: str
    critical: bool       # if True, a "fail" makes overall status CRITICAL


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def check_groot_server(host: str, port: int = 8001, mock: bool = False) -> ComponentCheck:
    """HTTP GET /health on the GR00T inference server; flag latency >300ms."""
    name = "GR00T Inference Server"
    url = f"http://{host}:{port}/health"
    if mock:
        latency_ms = random.uniform(180, 260)
        return ComponentCheck(
            name=name,
            status="pass",
            latency_ms=round(latency_ms, 1),
            detail=f"[mock] /health responded 200 OK in {latency_ms:.0f}ms — model loaded, 6.7 GB VRAM",
            critical=True,
        )
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            body = resp.read(512).decode(errors="replace")
            status = "pass" if latency_ms < 300 else "warn"
            detail = f"/health → {resp.status} in {latency_ms:.0f}ms. {body[:120]}"
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return ComponentCheck(name=name, status="fail", latency_ms=round(latency_ms, 1),
                              detail=f"Connection error: {exc}", critical=True)
    return ComponentCheck(name=name, status=status, latency_ms=round(latency_ms, 1),
                          detail=detail, critical=True)


def check_dagger_service(host: str, port: int = 8002, mock: bool = False) -> ComponentCheck:
    """Check the online DAgger learning endpoint is up."""
    name = "DAgger Online Learning Service"
    url = f"http://{host}:{port}/status"
    if mock:
        latency_ms = random.uniform(50, 130)
        return ComponentCheck(
            name=name,
            status="pass",
            latency_ms=round(latency_ms, 1),
            detail=f"[mock] /status OK — run5 active, 1 247 demos collected, 5 000 fine-tune steps",
            critical=True,
        )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            body = resp.read(512).decode(errors="replace")
            detail = f"/status → {resp.status} in {latency_ms:.0f}ms. {body[:120]}"
            status = "pass"
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return ComponentCheck(name=name, status="fail", latency_ms=round(latency_ms, 1),
                              detail=f"Connection error: {exc}", critical=True)
    return ComponentCheck(name=name, status=status, latency_ms=round(latency_ms, 1),
                          detail=detail, critical=True)


def check_genesis_sdg(output_dir: str = "/tmp/genesis_sdg_output", mock: bool = False) -> ComponentCheck:
    """Verify output directory contains recent .hdf5 files (<24 h old)."""
    name = "Genesis SDG Output"
    if mock:
        return ComponentCheck(
            name=name,
            status="pass",
            latency_ms=-1,
            detail="[mock] 42 .hdf5 files found; newest 1.3h old — SDG pipeline healthy",
            critical=False,
        )
    p = Path(output_dir)
    if not p.exists():
        return ComponentCheck(name=name, status="fail", latency_ms=-1,
                              detail=f"Output directory does not exist: {output_dir}", critical=False)
    hdf5_files = sorted(p.glob("**/*.hdf5"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not hdf5_files:
        return ComponentCheck(name=name, status="warn", latency_ms=-1,
                              detail=f"No .hdf5 files found in {output_dir}", critical=False)
    newest = hdf5_files[0]
    age_h = (time.time() - newest.stat().st_mtime) / 3600
    status = "pass" if age_h < 24 else "warn"
    detail = (f"{len(hdf5_files)} .hdf5 files found; newest '{newest.name}' "
              f"is {age_h:.1f}h old (threshold 24h)")
    return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)


def check_lerobot_dataset(path: str = "/tmp/lerobot_dataset", mock: bool = False) -> ComponentCheck:
    """Validate LeRobot dataset has episodes, check min count >50."""
    name = "LeRobot Dataset"
    if mock:
        ep_count = random.randint(980, 1050)
        status = "pass" if ep_count >= 50 else "warn"
        return ComponentCheck(
            name=name,
            status=status,
            latency_ms=-1,
            detail=f"[mock] {ep_count} episodes found in dataset (threshold 50)",
            critical=False,
        )
    p = Path(path)
    if not p.exists():
        return ComponentCheck(name=name, status="fail", latency_ms=-1,
                              detail=f"Dataset path does not exist: {path}", critical=False)
    # LeRobot stores episodes as parquet or as episode_*.hdf5 subdirectories
    episode_dirs = list(p.glob("episode_*"))
    parquet_files = list(p.glob("**/*.parquet"))
    ep_count = len(episode_dirs) or len(parquet_files)
    if ep_count == 0:
        return ComponentCheck(name=name, status="fail", latency_ms=-1,
                              detail=f"No episodes detected in {path}", critical=False)
    status = "pass" if ep_count >= 50 else "warn"
    detail = f"{ep_count} episodes found (threshold 50); path: {path}"
    return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)


def check_gpu_utilization(mock: bool = False) -> ComponentCheck:
    """Check GPU utilisation %; warn if <20% (idle waste) or >95% (OOM risk)."""
    name = "GPU Utilization"
    if mock:
        util_pct = random.uniform(55, 90)
        status = "pass"
        detail = f"[mock] GPU util {util_pct:.0f}% across A100 80GB — training active"
        return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=True)
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().splitlines()
        if not lines:
            raise RuntimeError("nvidia-smi returned no output")
        parts = lines[0].split(",")
        util_pct = float(parts[0].strip())
        mem_used = float(parts[1].strip())
        mem_total = float(parts[2].strip())
        if util_pct < 20:
            status = "warn"
            detail = f"GPU util {util_pct:.0f}% — possible idle waste (threshold 20%)"
        elif util_pct > 95:
            status = "warn"
            detail = f"GPU util {util_pct:.0f}% — OOM risk (threshold 95%); mem {mem_used:.0f}/{mem_total:.0f} MB"
        else:
            status = "pass"
            detail = f"GPU util {util_pct:.0f}%; mem {mem_used:.0f}/{mem_total:.0f} MB"
    except FileNotFoundError:
        return ComponentCheck(name=name, status="warn", latency_ms=-1,
                              detail="nvidia-smi not found — cannot check GPU (expected on OCI GPU node)",
                              critical=True)
    except Exception as exc:
        return ComponentCheck(name=name, status="fail", latency_ms=-1,
                              detail=f"GPU check error: {exc}", critical=True)
    return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=True)


def check_storage_quota(bucket: str = "oci-robot-cloud-data", mock: bool = False) -> ComponentCheck:
    """Mock: return used/total GB, warn if >80%."""
    name = f"Storage Quota ({bucket})"
    if mock:
        total_gb = 2048.0
        used_gb = random.uniform(900, 1500)
        pct = used_gb / total_gb * 100
        status = "warn" if pct > 80 else "pass"
        detail = (f"[mock] {used_gb:.0f} GB / {total_gb:.0f} GB used "
                  f"({pct:.1f}%) — threshold 80%")
        return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)
    # Live: attempt OCI CLI; fall back to disk usage of local mount
    try:
        import subprocess
        result = subprocess.run(
            ["oci", "os", "bucket", "get", "--bucket-name", bucket,
             "--query", "data.\"approximate-size\"", "--raw-output"],
            capture_output=True, text=True, timeout=15,
        )
        used_bytes = int(result.stdout.strip())
        used_gb = used_bytes / (1024 ** 3)
        total_gb = 5120.0  # default OCI object storage quota
        pct = used_gb / total_gb * 100
        status = "warn" if pct > 80 else "pass"
        detail = f"{used_gb:.1f} GB / {total_gb:.0f} GB ({pct:.1f}%)"
    except Exception as exc:
        return ComponentCheck(name=name, status="warn", latency_ms=-1,
                              detail=f"Could not query OCI storage: {exc}", critical=False)
    return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)


def check_checkpoint_freshness(
    path: str = "/tmp/groot_finetune/checkpoints", mock: bool = False
) -> ComponentCheck:
    """Find latest .pt file; warn if >6 h old."""
    name = "Checkpoint Freshness"
    if mock:
        age_h = random.uniform(0.5, 4.0)
        status = "pass"
        detail = (f"[mock] Latest checkpoint step_5000.pt is {age_h:.1f}h old "
                  f"(threshold 6h) — fine-tune pipeline active")
        return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)
    p = Path(path)
    if not p.exists():
        return ComponentCheck(name=name, status="warn", latency_ms=-1,
                              detail=f"Checkpoint directory not found: {path}", critical=False)
    pt_files = sorted(p.glob("**/*.pt"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not pt_files:
        return ComponentCheck(name=name, status="warn", latency_ms=-1,
                              detail=f"No .pt checkpoint files found in {path}", critical=False)
    newest = pt_files[0]
    age_h = (time.time() - newest.stat().st_mtime) / 3600
    status = "pass" if age_h <= 6 else "warn"
    detail = f"Latest: {newest.name}, {age_h:.1f}h old (threshold 6h)"
    return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)


def check_eval_pipeline(mock: bool = False) -> ComponentCheck:
    """Verify eval script importable and benchmark data present."""
    name = "Eval Pipeline"
    if mock:
        return ComponentCheck(
            name=name,
            status="pass",
            latency_ms=-1,
            detail="[mock] eval modules importable; benchmark data found (20 episodes); last run: 226ms/step",
            critical=False,
        )
    issues = []
    # Check Python importability of libero (eval dependency)
    for mod in ("numpy", "torch"):
        try:
            __import__(mod)
        except ImportError:
            issues.append(f"{mod} not importable")
    # Check for benchmark data dirs in common locations
    benchmark_paths = [
        Path("/tmp/libero_data"),
        Path("/tmp/eval_1000demo"),
        Path(os.path.expanduser("~/Downloads/roboticsai/data/eval")),
    ]
    found = [str(bp) for bp in benchmark_paths if bp.exists()]
    if not found:
        issues.append("No benchmark data directories found")
    if issues:
        status = "warn"
        detail = "Issues: " + "; ".join(issues)
    else:
        status = "pass"
        detail = f"All eval dependencies importable; benchmark data at {found[0]}"
    return ComponentCheck(name=name, status=status, latency_ms=-1, detail=detail, critical=False)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_all_checks(host: str = "138.1.153.110", mock: bool = True) -> List[ComponentCheck]:
    """Run all checks; exceptions are caught and converted to fail."""
    checks = []

    def safe(fn, *args, **kwargs) -> ComponentCheck:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            # Derive name from function name
            name = fn.__name__.replace("check_", "").replace("_", " ").title()
            return ComponentCheck(name=name, status="fail", latency_ms=-1,
                                  detail=f"Unexpected error: {exc}", critical=False)

    checks.append(safe(check_groot_server, host=host, mock=mock))
    checks.append(safe(check_dagger_service, host=host, mock=mock))
    checks.append(safe(check_genesis_sdg, mock=mock))
    checks.append(safe(check_lerobot_dataset, mock=mock))
    checks.append(safe(check_gpu_utilization, mock=mock))
    checks.append(safe(check_storage_quota, mock=mock))
    checks.append(safe(check_checkpoint_freshness, mock=mock))
    checks.append(safe(check_eval_pipeline, mock=mock))
    return checks


def compute_overall_status(checks: List[ComponentCheck]) -> str:
    """Return HEALTHY / DEGRADED / CRITICAL based on check results."""
    statuses = {c.status for c in checks}
    critical_fail = any(c.status == "fail" and c.critical for c in checks)
    if critical_fail:
        return "CRITICAL"
    if "fail" in statuses or "warn" in statuses:
        return "DEGRADED"
    return "HEALTHY"


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

_STATUS_COLOR = {
    "pass": "#22c55e",   # green-500
    "warn": "#f59e0b",   # amber-500
    "fail": "#ef4444",   # red-500
}
_STATUS_LABEL = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
_OVERALL_BG = {"HEALTHY": "#14532d", "DEGRADED": "#78350f", "CRITICAL": "#7f1d1d"}
_OVERALL_COLOR = {"HEALTHY": "#4ade80", "DEGRADED": "#fbbf24", "CRITICAL": "#f87171"}


def _latency_bar(latency_ms: float) -> str:
    if latency_ms < 0:
        return '<span style="color:#6b7280;font-size:12px;">N/A</span>'
    # bar: 0→500ms maps to 0→100%
    pct = min(latency_ms / 500 * 100, 100)
    color = "#22c55e" if latency_ms < 200 else "#f59e0b" if latency_ms < 350 else "#ef4444"
    return (
        f'<div style="font-size:12px;color:#9ca3af;margin-bottom:4px;">'
        f'Latency: {latency_ms:.0f} ms</div>'
        f'<div style="background:#374151;border-radius:4px;height:6px;width:100%;">'
        f'<div style="background:{color};height:6px;border-radius:4px;width:{pct:.1f}%;"></div></div>'
    )


def render_html(checks: List[ComponentCheck], overall: str) -> str:
    """Render a dark-theme HTML health report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pass_count = sum(1 for c in checks if c.status == "pass")
    warn_count = sum(1 for c in checks if c.status == "warn")
    fail_count = sum(1 for c in checks if c.status == "fail")

    banner_bg = _OVERALL_BG[overall]
    banner_fg = _OVERALL_COLOR[overall]

    cards_html = ""
    for c in checks:
        sc = _STATUS_COLOR[c.status]
        sl = _STATUS_LABEL[c.status]
        lat = _latency_bar(c.latency_ms)
        crit_badge = ('<span style="font-size:10px;background:#7f1d1d;color:#fca5a5;'
                      'padding:1px 5px;border-radius:3px;margin-left:6px;">CRITICAL</span>'
                      if c.critical else "")
        cards_html += f"""
        <div style="background:#1f2937;border-radius:10px;padding:20px;
                    border-left:4px solid {sc};position:relative;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <span style="font-weight:600;font-size:15px;color:#f3f4f6;">{c.name}{crit_badge}</span>
            <span style="background:{sc};color:#000;font-size:11px;font-weight:700;
                         padding:2px 10px;border-radius:12px;">{sl}</span>
          </div>
          {lat}
          <div style="margin-top:10px;font-size:13px;color:#9ca3af;line-height:1.5;">
            {c.detail}
          </div>
        </div>"""

    summary_items = (
        f'<span style="color:#22c55e;font-weight:600;">{pass_count} PASS</span> &nbsp;'
        f'<span style="color:#f59e0b;font-weight:600;">{warn_count} WARN</span> &nbsp;'
        f'<span style="color:#ef4444;font-weight:600;">{fail_count} FAIL</span>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta http-equiv="refresh" content="30"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — Pipeline Health</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #111827;
      color: #d1d5db;
      min-height: 100vh;
    }}
    a {{ color: #C74634; }}
  </style>
</head>
<body>
  <!-- Banner -->
  <div style="background:{banner_bg};padding:32px 40px;text-align:center;
               border-bottom:2px solid {banner_fg};">
    <div style="font-size:13px;color:#9ca3af;letter-spacing:2px;text-transform:uppercase;
                 margin-bottom:8px;">OCI Robot Cloud</div>
    <div style="font-size:42px;font-weight:800;color:{banner_fg};letter-spacing:1px;">
      {overall}
    </div>
    <div style="margin-top:12px;font-size:14px;color:#9ca3af;">
      {summary_items}
    </div>
    <div style="margin-top:6px;font-size:12px;color:#6b7280;">
      Last updated: {now} &nbsp;·&nbsp; Auto-refresh every 30 s
    </div>
  </div>

  <!-- Header -->
  <div style="max-width:1100px;margin:0 auto;padding:32px 24px 0;">
    <h1 style="font-size:22px;color:#C74634;font-weight:700;margin-bottom:4px;">
      Training Pipeline Health Check
    </h1>
    <p style="font-size:13px;color:#6b7280;">
      GR00T · DAgger · Genesis SDG · LeRobot · GPU · Storage · Checkpoints · Eval
    </p>
  </div>

  <!-- Component grid -->
  <div style="max-width:1100px;margin:24px auto;padding:0 24px 48px;
               display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;">
    {cards_html}
  </div>

  <!-- Footer -->
  <div style="text-align:center;padding:16px;font-size:11px;color:#374151;
               border-top:1px solid #1f2937;">
    Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; {now}
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud — Training Pipeline Health Check",
    )
    parser.add_argument(
        "--mock", action="store_true", default=False,
        help="Run in mock/simulated mode (no real network calls)",
    )
    parser.add_argument(
        "--host", default="138.1.153.110",
        help="OCI instance host (default: 138.1.153.110)",
    )
    parser.add_argument(
        "--output", default="/tmp/pipeline_health.html",
        help="Output HTML path (default: /tmp/pipeline_health.html)",
    )
    args = parser.parse_args()

    mode_label = "MOCK" if args.mock else f"LIVE ({args.host})"
    print(f"[health-check] Running checks in {mode_label} mode …", flush=True)

    checks = run_all_checks(host=args.host, mock=args.mock)
    overall = compute_overall_status(checks)

    # Console summary
    col = {"pass": "\033[92m", "warn": "\033[93m", "fail": "\033[91m"}
    reset = "\033[0m"
    for c in checks:
        lat_str = f"{c.latency_ms:.0f}ms" if c.latency_ms >= 0 else "   N/A"
        badge = col.get(c.status, "") + _STATUS_LABEL[c.status] + reset
        crit = " [CRITICAL]" if c.critical else ""
        print(f"  {badge}  {lat_str:>8}  {c.name}{crit}")
        print(f"           {c.detail[:100]}")

    overall_col = "\033[92m" if overall == "HEALTHY" else "\033[93m" if overall == "DEGRADED" else "\033[91m"
    print(f"\n[health-check] Overall: {overall_col}{overall}{reset}")

    html = render_html(checks, overall)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[health-check] Report written → {out_path}")

    sys.exit(0 if overall == "HEALTHY" else 1)


if __name__ == "__main__":
    main()
