#!/usr/bin/env python3
"""model_serving_load_tester.py — Load-test the GR00T inference serving infrastructure.

Simulates concurrent requests at various RPS levels and measures latency,
throughput, and error rates.  Supports both mock mode (M/M/1 queue simulation)
and live mode (real HTTP requests to the serving endpoint).

Usage:
    python model_serving_load_tester.py --mock --output /tmp/load_test.html
    python model_serving_load_tester.py --rps-levels 1,2,4,8,16,32 \
        --output /tmp/load_test.html
"""

import argparse
import json
import math
import random
import statistics
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LoadTestConfig:
    target_url: str = "http://localhost:8001/predict"
    rps_levels: List[int] = field(default_factory=lambda: [1, 2, 4, 8, 16, 32])
    duration_s: int = 30
    n_warmup: int = 5
    timeout_ms: int = 5000
    concurrency: int = 32


@dataclass
class RequestResult:
    timestamp: float          # unix epoch
    latency_ms: float
    status_code: int
    error: bool
    rps_actual: float


@dataclass
class LoadTestResult:
    rps_target: int
    rps_actual: float
    p50: float
    p90: float
    p95: float
    p99: float
    error_rate: float
    throughput_rps: float
    saturation_point: bool    # True if this level is the saturation point


# ---------------------------------------------------------------------------
# M/M/1 queue simulation helpers
# ---------------------------------------------------------------------------

# A100 baseline: ~226 ms mean service time  →  service rate ≈ 4.42 req/s per worker
_A100_MEAN_SERVICE_MS = 226.0
_A100_SERVICE_RATE = 1000.0 / _A100_MEAN_SERVICE_MS   # req/s
_SATURATION_RHO = 0.95        # utilisation threshold → ~12 RPS saturates
_SATURATION_RPS = _A100_SERVICE_RATE * _SATURATION_RHO   # ≈ 12 RPS


def _mm1_mean_wait_ms(arrival_rate: float, service_rate: float) -> float:
    """Expected waiting time (ms) in an M/M/1 queue (Pollaczek–Khinchine)."""
    rho = arrival_rate / service_rate
    if rho >= 1.0:
        # Queue is unstable — return a very large number
        return 5000.0 + (rho - 1.0) * 20_000.0
    # E[W] = rho / (mu * (1-rho)) in seconds, convert to ms
    wait_s = rho / (service_rate * (1.0 - rho))
    return wait_s * 1000.0


def _gamma_sample(rng: random.Random, mean: float, cv: float = 0.5) -> float:
    """Sample from a Gamma distribution with given mean and coefficient of variation."""
    # shape k = 1/cv^2, scale theta = mean/k
    k = 1.0 / (cv ** 2)
    theta = mean / k
    return rng.gammavariate(k, theta)


def _simulate_single_rps(
    rps_target: int,
    duration_s: int,
    n_warmup: int,
    rng: random.Random,
) -> List[RequestResult]:
    """Simulate `duration_s` seconds of load at `rps_target` using M/M/1 theory."""
    service_rate = _A100_SERVICE_RATE
    arrival_rate = float(rps_target)

    rho = arrival_rate / service_rate
    mean_wait_ms = _mm1_mean_wait_ms(arrival_rate, service_rate)
    mean_service_ms = _A100_MEAN_SERVICE_MS

    # Latency = wait_in_queue + service_time
    # We add Gaussian jitter to make it realistic
    total_requests = rps_target * (duration_s + n_warmup)
    results: List[RequestResult] = []
    t = 0.0
    inter_arrival = 1.0 / rps_target  # seconds

    for i in range(total_requests):
        t += inter_arrival + rng.gauss(0, inter_arrival * 0.05)

        # Service time ~ Gamma(mean=226ms, cv=0.4)
        service_ms = _gamma_sample(rng, mean_service_ms, cv=0.4)
        service_ms = max(50.0, service_ms)

        # Queue wait ~ Exp(mean=mean_wait_ms) when stable; inflated when overloaded
        if rho < 1.0:
            wait_ms = rng.expovariate(1.0 / (mean_wait_ms + 1e-9)) if mean_wait_ms > 0 else 0.0
        else:
            # Overload: wait grows proportionally
            wait_ms = mean_wait_ms * rng.uniform(0.8, 1.4)

        latency_ms = service_ms + wait_ms

        # Error modelling:
        # - baseline ~0.1% error
        # - spikes above 28 RPS → climbs to ~8%
        base_err = 0.001
        if rps_target >= 28:
            base_err = 0.08 * ((rps_target - 27) / 5.0)
        elif rps_target >= 20:
            base_err = 0.015
        elif rps_target >= 16:
            base_err = 0.005

        is_error = rng.random() < base_err
        # Timeout — treat latency > 5000 ms as an error
        if latency_ms > 4900:
            is_error = True
            latency_ms = 5000.0

        status = 500 if is_error else 200

        results.append(RequestResult(
            timestamp=t,
            latency_ms=latency_ms,
            status_code=status,
            error=is_error,
            rps_actual=arrival_rate,
        ))

    # Drop warmup requests
    return results[n_warmup:]


def _compute_percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(math.ceil(p / 100.0 * len(sorted_vals))) - 1
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return sorted_vals[idx]


# ---------------------------------------------------------------------------
# Core simulation entry point
# ---------------------------------------------------------------------------

def simulate_load_test(
    config: LoadTestConfig,
    seed: int = 42,
) -> List[LoadTestResult]:
    """Run mock load test across all RPS levels in config and return results."""
    rng = random.Random(seed)
    results: List[LoadTestResult] = []

    for rps in config.rps_levels:
        raw = _simulate_single_rps(
            rps_target=rps,
            duration_s=config.duration_s,
            n_warmup=config.n_warmup,
            rng=rng,
        )

        latencies = sorted(r.latency_ms for r in raw if not r.error)
        all_latencies = sorted(r.latency_ms for r in raw)
        errors = sum(1 for r in raw if r.error)
        total = len(raw)

        p50 = _compute_percentile(latencies, 50) if latencies else 0.0
        p90 = _compute_percentile(latencies, 90) if latencies else 0.0
        p95 = _compute_percentile(latencies, 95) if latencies else 0.0
        p99 = _compute_percentile(latencies, 99) if latencies else 0.0

        error_rate = errors / total if total > 0 else 0.0

        # Actual throughput = successful reqs / duration
        successful = total - errors
        throughput = successful / config.duration_s

        actual_rps = round(total / config.duration_s, 2)

        results.append(LoadTestResult(
            rps_target=rps,
            rps_actual=actual_rps,
            p50=round(p50, 1),
            p90=round(p90, 1),
            p95=round(p95, 1),
            p99=round(p99, 1),
            error_rate=round(error_rate, 4),
            throughput_rps=round(throughput, 2),
            saturation_point=False,  # filled in by find_saturation_point
        ))

    return results


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def find_saturation_point(results: List[LoadTestResult]) -> Optional[int]:
    """Return the RPS target where p95 > 400 ms or error_rate > 0.01.

    Returns None if no saturation is detected across the provided levels.
    """
    for r in results:
        if r.p95 > 400.0 or r.error_rate > 0.01:
            return r.rps_target
    return None


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def render_html(results: List[LoadTestResult], saturation: Optional[int]) -> str:
    """Render a dark-theme HTML report with Chart.js inline via CDN."""

    rps_labels = [str(r.rps_target) for r in results]
    p50_data   = [r.p50 for r in results]
    p95_data   = [r.p95 for r in results]
    p99_data   = [r.p99 for r in results]
    tput_data  = [r.throughput_rps for r in results]
    err_data   = [round(r.error_rate * 100, 2) for r in results]

    # Recommended operating point: last level BEFORE saturation
    rec_idx: Optional[int] = None
    if saturation is not None:
        for i, r in enumerate(results):
            if r.rps_target < saturation:
                rec_idx = i
    elif results:
        rec_idx = len(results) - 1

    # Saturation annotation band
    sat_annotation_js = "null"
    if saturation is not None:
        sat_annotation_js = f"""{{
            type: 'box',
            xMin: {rps_labels.index(str(saturation)) - 0.5},
            xMax: {len(rps_labels) - 0.5},
            backgroundColor: 'rgba(239,68,68,0.15)',
            borderColor: 'rgba(239,68,68,0.5)',
            borderWidth: 1,
            label: {{ content: 'Saturation Zone', display: true, color: '#f87171', font: {{ size: 11 }} }}
        }}"""

    rec_annotation_js = "null"
    if rec_idx is not None:
        rec_annotation_js = f"""{{
            type: 'line',
            xMin: {rec_idx},
            xMax: {rec_idx},
            borderColor: '#34d399',
            borderWidth: 2,
            borderDash: [6,3],
            label: {{
                content: 'Recommended: {results[rec_idx].rps_target} RPS',
                display: true, color: '#34d399', font: {{ size: 11 }},
                position: 'start'
            }}
        }}"""

    # SLA compliance table rows
    sla_rows = ""
    for r in results:
        sat_badge = (
            '<span style="color:#f87171;font-weight:700">SATURATED</span>'
            if r.saturation_point else
            '<span style="color:#34d399">OK</span>'
        )
        p95_ok = r.p95 <= 400.0
        err_ok = r.error_rate <= 0.01
        sla_rows += f"""
            <tr>
                <td>{r.rps_target}</td>
                <td>{r.rps_actual:.1f}</td>
                <td style="color:{'#34d399' if p95_ok else '#f87171'}">{r.p95:.0f} ms</td>
                <td>{r.p99:.0f} ms</td>
                <td style="color:{'#34d399' if err_ok else '#f87171'}">{r.error_rate*100:.2f}%</td>
                <td>{r.throughput_rps:.1f}</td>
                <td>{sat_badge}</td>
            </tr>"""

    sat_label = f"{saturation} RPS" if saturation else "Not detected"
    rec_label = (
        f"{results[rec_idx].rps_target} RPS" if rec_idx is not None else "N/A"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GR00T Load Test Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f172a; color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 2rem;
  }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; margin-bottom: .25rem; }}
  .subtitle {{ color: #94a3b8; font-size: .9rem; margin-bottom: 2rem; }}
  .kpi-row {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
    gap: 1rem; margin-bottom: 2rem;
  }}
  .kpi {{
    background: #1e293b; border: 1px solid #334155;
    border-radius: .75rem; padding: 1rem 1.25rem;
  }}
  .kpi .label {{ font-size: .75rem; color: #94a3b8; text-transform: uppercase; letter-spacing:.05em; }}
  .kpi .value {{ font-size: 1.5rem; font-weight: 700; color: #f1f5f9; margin-top:.25rem; }}
  .kpi .value.warn {{ color: #fb923c; }}
  .grid-2 {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 1.5rem; margin-bottom: 1.5rem;
  }}
  @media (max-width: 900px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .card {{
    background: #1e293b; border: 1px solid #334155;
    border-radius: .75rem; padding: 1.25rem;
  }}
  .card h2 {{ font-size: 1rem; font-weight: 600; color: #cbd5e1; margin-bottom: 1rem; }}
  canvas {{ width: 100% !important; height: 260px !important; }}
  table {{
    width: 100%; border-collapse: collapse; font-size: .85rem; margin-top: .5rem;
  }}
  th {{
    background: #0f172a; color: #94a3b8; text-align: left;
    padding: .5rem .75rem; font-weight: 600;
    border-bottom: 1px solid #334155;
  }}
  td {{ padding: .5rem .75rem; border-bottom: 1px solid #1e293b; color: #e2e8f0; }}
  tr:hover td {{ background: #0f172a22; }}
  .footer {{ color: #475569; font-size: .75rem; margin-top: 2rem; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Inference Serving — Load Test Report</h1>
<p class="subtitle">A100 GPU · GR00T N1.6 · Simulation via M/M/1 queue model</p>

<div class="kpi-row">
  <div class="kpi">
    <div class="label">Saturation Point</div>
    <div class="value warn">{sat_label}</div>
  </div>
  <div class="kpi">
    <div class="label">Recommended Operating</div>
    <div class="value">{rec_label}</div>
  </div>
  <div class="kpi">
    <div class="label">Baseline Latency (p50)</div>
    <div class="value">{results[0].p50:.0f} ms</div>
  </div>
  <div class="kpi">
    <div class="label">SLA p95 &lt; 400 ms up to</div>
    <div class="value">{"N/A" if saturation is None else (str(saturation - 1) + " RPS" if saturation > 1 else "Saturated at start")}</div>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>Latency vs RPS (p50 / p95 / p99)</h2>
    <canvas id="latencyChart"></canvas>
  </div>
  <div class="card">
    <h2>Throughput (successful req/s)</h2>
    <canvas id="throughputChart"></canvas>
  </div>
</div>

<div class="grid-2">
  <div class="card">
    <h2>Error Rate (%)</h2>
    <canvas id="errorChart"></canvas>
  </div>
  <div class="card">
    <h2>SLA Compliance</h2>
    <table>
      <thead>
        <tr>
          <th>RPS Target</th><th>RPS Actual</th><th>p95</th>
          <th>p99</th><th>Error Rate</th><th>Throughput</th><th>Status</th>
        </tr>
      </thead>
      <tbody>{sla_rows}</tbody>
    </table>
  </div>
</div>

<p class="footer">Generated by model_serving_load_tester.py · OCI Robot Cloud</p>

<script>
const labels = {json.dumps(rps_labels)};
const p50    = {json.dumps(p50_data)};
const p95    = {json.dumps(p95_data)};
const p99    = {json.dumps(p99_data)};
const tput   = {json.dumps(tput_data)};
const errPct = {json.dumps(err_data)};

const gridColor = '#334155';
const commonOpts = (yLabel) => ({{
  responsive: true,
  maintainAspectRatio: false,
  plugins: {{
    legend: {{ labels: {{ color: '#94a3b8', boxWidth: 12 }} }},
    annotation: {{
      annotations: {{
        satZone: {sat_annotation_js},
        recLine: {rec_annotation_js},
      }}
    }}
  }},
  scales: {{
    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: gridColor }},
          title: {{ display: true, text: 'RPS Target', color: '#94a3b8' }} }},
    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: gridColor }},
          title: {{ display: true, text: yLabel, color: '#94a3b8' }} }},
  }}
}});

// Latency chart
new Chart(document.getElementById('latencyChart'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [
      {{ label: 'p50', data: p50, borderColor: '#60a5fa', backgroundColor: '#60a5fa22',
         tension: 0.35, pointRadius: 4, fill: false }},
      {{ label: 'p95', data: p95, borderColor: '#fb923c', backgroundColor: '#fb923c22',
         tension: 0.35, pointRadius: 4, fill: false }},
      {{ label: 'p99', data: p99, borderColor: '#f472b6', backgroundColor: '#f472b622',
         tension: 0.35, pointRadius: 4, fill: false }},
    ]
  }},
  options: {{
    ...commonOpts('Latency (ms)'),
    plugins: {{
      ...commonOpts('Latency (ms)').plugins,
      annotation: {{
        annotations: {{
          slaLine: {{
            type: 'line', yMin: 400, yMax: 400,
            borderColor: '#ef4444', borderWidth: 1.5, borderDash: [5,3],
            label: {{ content: 'SLA 400ms', display: true, color: '#ef4444',
                      font: {{ size: 10 }}, position: 'end' }}
          }},
          satZone: {sat_annotation_js},
          recLine: {rec_annotation_js},
        }}
      }}
    }}
  }}
}});

// Throughput chart
new Chart(document.getElementById('throughputChart'), {{
  type: 'bar',
  data: {{
    labels,
    datasets: [{{
      label: 'Throughput (req/s)',
      data: tput,
      backgroundColor: labels.map((_, i) => {{
        const sat = {json.dumps(list(rps_labels.index(str(saturation)) if saturation and str(saturation) in rps_labels else len(rps_labels)))};
        return i >= sat ? '#ef444466' : '#34d39966';
      }}),
      borderColor: labels.map((_, i) => {{
        const sat = {json.dumps(list(rps_labels.index(str(saturation)) if saturation and str(saturation) in rps_labels else len(rps_labels)))};
        return i >= sat ? '#ef4444' : '#34d399';
      }}),
      borderWidth: 1,
    }}]
  }},
  options: commonOpts('req/s')
}});

// Error rate chart
new Chart(document.getElementById('errorChart'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [{{
      label: 'Error Rate (%)',
      data: errPct,
      borderColor: '#f87171',
      backgroundColor: '#f8717133',
      tension: 0.35,
      pointRadius: 5,
      fill: true,
    }}]
  }},
  options: {{
    ...commonOpts('Error Rate (%)'),
    plugins: {{
      ...commonOpts('Error Rate (%)').plugins,
      annotation: {{
        annotations: {{
          slaErr: {{
            type: 'line', yMin: 1, yMax: 1,
            borderColor: '#fb923c', borderWidth: 1.5, borderDash: [5,3],
            label: {{ content: 'SLA 1%', display: true, color: '#fb923c',
                      font: {{ size: 10 }}, position: 'end' }}
          }},
        }}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Live load test (non-mock)
# ---------------------------------------------------------------------------

def _live_load_test(config: LoadTestConfig) -> List[LoadTestResult]:
    """Issue real HTTP requests to config.target_url and measure latency."""
    import queue
    import threading

    results: List[LoadTestResult] = []

    dummy_payload = json.dumps({
        "observation": {"image": "", "state": [0.0] * 7},
        "language_instruction": "pick up the cube",
    }).encode()

    for rps in config.rps_levels:
        print(f"  Testing {rps} RPS for {config.duration_s}s ...", flush=True)
        raw: List[RequestResult] = []
        lock = threading.Lock()

        def _worker(ts: float, actual_rps: float) -> None:
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(
                    config.target_url,
                    data=dummy_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                timeout_s = config.timeout_ms / 1000.0
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    _ = resp.read()
                    code = resp.status
                    is_err = False
            except Exception:
                code = 500
                is_err = True
            lat = (time.perf_counter() - t0) * 1000.0
            with lock:
                raw.append(RequestResult(
                    timestamp=ts,
                    latency_ms=lat,
                    status_code=code,
                    error=is_err,
                    rps_actual=actual_rps,
                ))

        interval = 1.0 / rps
        total = rps * (config.duration_s + config.n_warmup)
        threads = []
        t_start = time.perf_counter()
        for i in range(total):
            t = threading.Thread(target=_worker, args=(time.perf_counter(), float(rps)))
            t.daemon = True
            threads.append(t)
            t.start()
            elapsed = time.perf_counter() - t_start
            expected = (i + 1) * interval
            sleep_t = expected - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        for t in threads:
            t.join(timeout=config.timeout_ms / 1000.0 + 1)

        # Drop warmup
        data = sorted(raw, key=lambda r: r.timestamp)[config.n_warmup:]
        latencies = sorted(r.latency_ms for r in data if not r.error)
        errors = sum(1 for r in data if r.error)
        total_req = len(data)

        p50 = _compute_percentile(latencies, 50) if latencies else 0.0
        p90 = _compute_percentile(latencies, 90) if latencies else 0.0
        p95 = _compute_percentile(latencies, 95) if latencies else 0.0
        p99 = _compute_percentile(latencies, 99) if latencies else 0.0
        error_rate = errors / total_req if total_req > 0 else 0.0
        throughput = (total_req - errors) / config.duration_s

        results.append(LoadTestResult(
            rps_target=rps,
            rps_actual=round(total_req / config.duration_s, 2),
            p50=round(p50, 1),
            p90=round(p90, 1),
            p95=round(p95, 1),
            p99=round(p99, 1),
            error_rate=round(error_rate, 4),
            throughput_rps=round(throughput, 2),
            saturation_point=False,
        ))

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Load-test GR00T inference serving infrastructure."
    )
    p.add_argument(
        "--mock", action="store_true",
        help="Use simulated M/M/1 queue model instead of live HTTP requests.",
    )
    p.add_argument(
        "--url", default="http://localhost:8001/predict",
        help="Target URL for live load test (default: %(default)s).",
    )
    p.add_argument(
        "--rps-levels", default="1,2,4,8,16,32",
        help="Comma-separated RPS levels to test (default: %(default)s).",
    )
    p.add_argument(
        "--duration", type=int, default=30,
        help="Duration in seconds per RPS level (default: %(default)s).",
    )
    p.add_argument(
        "--warmup", type=int, default=5,
        help="Number of warmup requests per level (default: %(default)s).",
    )
    p.add_argument(
        "--timeout-ms", type=int, default=5000,
        help="Request timeout in milliseconds (default: %(default)s).",
    )
    p.add_argument(
        "--output", default="/tmp/load_test.html",
        help="Path for HTML report output (default: %(default)s).",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for simulation (default: %(default)s).",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    rps_levels = [int(x.strip()) for x in args.rps_levels.split(",") if x.strip()]

    config = LoadTestConfig(
        target_url=args.url,
        rps_levels=rps_levels,
        duration_s=args.duration,
        n_warmup=args.warmup,
        timeout_ms=args.timeout_ms,
        concurrency=32,
    )

    print(f"GR00T Load Tester — {'MOCK' if args.mock else 'LIVE'} mode")
    print(f"RPS levels : {rps_levels}")
    print(f"Duration   : {config.duration_s}s per level")
    if not args.mock:
        print(f"Target URL : {config.target_url}")
    print()

    if args.mock:
        print("Running simulated load test...")
        results = simulate_load_test(config, seed=args.seed)
    else:
        print("Running live load test...")
        results = _live_load_test(config)

    saturation = find_saturation_point(results)

    # Mark saturation point on results
    if saturation is not None:
        for r in results:
            if r.rps_target == saturation:
                r.saturation_point = True

    # Print summary table
    print(f"\n{'RPS':>6} {'p50':>8} {'p95':>8} {'p99':>8} {'err%':>7} {'tput':>7}")
    print("-" * 50)
    for r in results:
        sat_mark = " *SAT*" if r.saturation_point else ""
        print(
            f"{r.rps_target:>6} {r.p50:>7.0f}ms {r.p95:>7.0f}ms "
            f"{r.p99:>7.0f}ms {r.error_rate*100:>6.2f}% {r.throughput_rps:>6.1f}{sat_mark}"
        )

    if saturation:
        print(f"\n[!] Saturation detected at {saturation} RPS (p95 > 400ms or error_rate > 1%)")
    else:
        print("\n[OK] No saturation detected across tested RPS levels.")

    html = render_html(results, saturation)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"\nHTML report written to: {args.output}")


if __name__ == "__main__":
    main()
