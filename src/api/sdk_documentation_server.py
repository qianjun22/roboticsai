#!/usr/bin/env python3
"""
sdk_documentation_server.py — OCI Robot Cloud SDK Documentation Portal (port 8033)

Serves a fully self-contained HTML reference for all OCI Robot Cloud APIs, the Python SDK,
CLI commands, data formats, and runnable examples. Intended for design partners during
private beta access.

Sections:
  1. Python SDK   — RobotCloudClient methods with parameters, return types, code examples
  2. REST API     — 50+ endpoints organized by service (ports 8001–8050), searchable table
  3. CLI Reference — oci-robot-cloud commands with flags and examples
  4. Data Formats — LeRobot v2 episode schema, checkpoint structure, eval JSON schema
  5. Examples     — Quickstart, DAgger loop, cross-embodiment runnable scripts

JSON endpoints:
  GET /api/endpoints   — full endpoint catalog (for SDK auto-discovery)
  GET /health          — uptime check

Usage:
    pip install fastapi uvicorn
    python src/api/sdk_documentation_server.py
    # open http://localhost:8033

Production (OCI):
    uvicorn src.api.sdk_documentation_server:app --host 0.0.0.0 --port 8033
"""

import json
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    print("pip install fastapi uvicorn")
    raise

# ── Endpoint Catalog ─────────────────────────────────────────────────────────
# This is the single source of truth — rendered into both the HTML table and
# the /api/endpoints JSON response.

ENDPOINTS: list[dict[str, str]] = [
    # ── Inference Service (8001) ──────────────────────────────────────────────
    {"port": "8001", "method": "GET",    "path": "/health",                        "service": "Inference",        "auth": "None",   "description": "Liveness check; returns {status, model, uptime_s}"},
    {"port": "8001", "method": "POST",   "path": "/predict",                       "service": "Inference",        "auth": "Bearer", "description": "Run one forward pass; body: {observation, lang_instruction}; returns {action_chunk}"},
    {"port": "8001", "method": "POST",   "path": "/predict/batch",                 "service": "Inference",        "auth": "Bearer", "description": "Batch inference up to 32 observations in one call"},
    {"port": "8001", "method": "GET",    "path": "/model/info",                    "service": "Inference",        "auth": "Bearer", "description": "Returns loaded model ID, parameter count, embodiment config"},
    {"port": "8001", "method": "POST",   "path": "/model/load",                    "service": "Inference",        "auth": "Bearer", "description": "Hot-swap checkpoint; body: {checkpoint_id}"},
    {"port": "8001", "method": "GET",    "path": "/metrics",                       "service": "Inference",        "auth": "Bearer", "description": "Prometheus-format latency/throughput metrics"},

    # ── Fine-Tune API (8080) ──────────────────────────────────────────────────
    {"port": "8080", "method": "POST",   "path": "/jobs/train",                    "service": "Fine-Tune",        "auth": "Bearer", "description": "Submit a training job; body: TrainRequest; returns {job_id}"},
    {"port": "8080", "method": "GET",    "path": "/jobs/{job_id}/status",          "service": "Fine-Tune",        "auth": "Bearer", "description": "Poll job state: pending | running | done | failed"},
    {"port": "8080", "method": "GET",    "path": "/jobs/{job_id}/results",         "service": "Fine-Tune",        "auth": "Bearer", "description": "Returns {mae, final_loss, checkpoint_url, cost_usd, duration_s}"},
    {"port": "8080", "method": "GET",    "path": "/jobs/{job_id}/logs",            "service": "Fine-Tune",        "auth": "Bearer", "description": "Stream training log lines via SSE"},
    {"port": "8080", "method": "DELETE", "path": "/jobs/{job_id}",                 "service": "Fine-Tune",        "auth": "Bearer", "description": "Cancel a running or pending job"},
    {"port": "8080", "method": "GET",    "path": "/jobs",                          "service": "Fine-Tune",        "auth": "Bearer", "description": "List all jobs for the authenticated tenant; supports ?limit=&after="},
    {"port": "8080", "method": "POST",   "path": "/jobs/{job_id}/deploy",          "service": "Fine-Tune",        "auth": "Bearer", "description": "Package checkpoint as Jetson-ready tarball; returns {download_url}"},
    {"port": "8080", "method": "GET",    "path": "/pricing",                       "service": "Fine-Tune",        "auth": "None",   "description": "Returns current cost per GPU-hour and estimated cost formula"},
    {"port": "8080", "method": "GET",    "path": "/health",                        "service": "Fine-Tune",        "auth": "None",   "description": "Service liveness"},

    # ── Data Collection API (8003) ────────────────────────────────────────────
    {"port": "8003", "method": "POST",   "path": "/episodes",                      "service": "Data Collection",  "auth": "Bearer", "description": "Upload a new LeRobot v2 episode (multipart/form-data)"},
    {"port": "8003", "method": "GET",    "path": "/episodes",                      "service": "Data Collection",  "auth": "Bearer", "description": "List uploaded episodes with metadata and frame counts"},
    {"port": "8003", "method": "GET",    "path": "/episodes/{episode_id}",         "service": "Data Collection",  "auth": "Bearer", "description": "Fetch episode metadata and download URL"},
    {"port": "8003", "method": "DELETE", "path": "/episodes/{episode_id}",         "service": "Data Collection",  "auth": "Bearer", "description": "Remove episode from dataset"},
    {"port": "8003", "method": "POST",   "path": "/datasets",                      "service": "Data Collection",  "auth": "Bearer", "description": "Create a named dataset from a list of episode IDs"},
    {"port": "8003", "method": "GET",    "path": "/datasets",                      "service": "Data Collection",  "auth": "Bearer", "description": "List datasets with episode count and size_mb"},
    {"port": "8003", "method": "GET",    "path": "/datasets/{dataset_id}/stats",   "service": "Data Collection",  "auth": "Bearer", "description": "Per-joint trajectory statistics for quality review"},
    {"port": "8003", "method": "GET",    "path": "/health",                        "service": "Data Collection",  "auth": "None",   "description": "Service liveness"},

    # ── Model Registry (8010) ────────────────────────────────────────────────
    {"port": "8010", "method": "GET",    "path": "/checkpoints",                   "service": "Model Registry",   "auth": "Bearer", "description": "List all stored checkpoints across jobs"},
    {"port": "8010", "method": "GET",    "path": "/checkpoints/{checkpoint_id}",   "service": "Model Registry",   "auth": "Bearer", "description": "Returns checkpoint metadata: job_id, step, mae, loss, created_at"},
    {"port": "8010", "method": "POST",   "path": "/checkpoints/{id}/promote",      "service": "Model Registry",   "auth": "Bearer", "description": "Tag a checkpoint as 'production'; only one per embodiment"},
    {"port": "8010", "method": "DELETE", "path": "/checkpoints/{checkpoint_id}",   "service": "Model Registry",   "auth": "Bearer", "description": "Delete checkpoint and free OCI object storage"},
    {"port": "8010", "method": "GET",    "path": "/models/production",             "service": "Model Registry",   "auth": "Bearer", "description": "Returns the current production checkpoint per embodiment"},
    {"port": "8010", "method": "GET",    "path": "/health",                        "service": "Model Registry",   "auth": "None",   "description": "Service liveness"},

    # ── Evaluation Service (8012) ────────────────────────────────────────────
    {"port": "8012", "method": "POST",   "path": "/eval/run",                      "service": "Evaluation",       "auth": "Bearer", "description": "Launch LIBERO eval; body: {checkpoint_id, task_suite, n_episodes}"},
    {"port": "8012", "method": "GET",    "path": "/eval/{eval_id}/status",         "service": "Evaluation",       "auth": "Bearer", "description": "Poll eval state: queued | running | done | failed"},
    {"port": "8012", "method": "GET",    "path": "/eval/{eval_id}/results",        "service": "Evaluation",       "auth": "Bearer", "description": "Returns {success_rate, mean_reward, per_task_breakdown, video_url}"},
    {"port": "8012", "method": "GET",    "path": "/eval/compare",                  "service": "Evaluation",       "auth": "Bearer", "description": "Compare two checkpoints side-by-side; ?a=<id>&b=<id>"},
    {"port": "8012", "method": "GET",    "path": "/health",                        "service": "Evaluation",       "auth": "None",   "description": "Service liveness"},

    # ── DAgger Service (8015) ────────────────────────────────────────────────
    {"port": "8015", "method": "POST",   "path": "/dagger/runs",                   "service": "DAgger",           "auth": "Bearer", "description": "Start a DAgger iteration; body: {base_checkpoint_id, n_rollouts, mix_ratio}"},
    {"port": "8015", "method": "GET",    "path": "/dagger/runs/{run_id}/status",   "service": "DAgger",           "auth": "Bearer", "description": "Poll DAgger run state and current iteration"},
    {"port": "8015", "method": "GET",    "path": "/dagger/runs/{run_id}/history",  "service": "DAgger",           "auth": "Bearer", "description": "Returns per-iteration success rates and loss values"},
    {"port": "8015", "method": "POST",   "path": "/dagger/runs/{run_id}/stop",     "service": "DAgger",           "auth": "Bearer", "description": "Gracefully stop after current iteration completes"},
    {"port": "8015", "method": "GET",    "path": "/health",                        "service": "DAgger",           "auth": "None",   "description": "Service liveness"},

    # ── Telemetry / Monitoring (8020) ────────────────────────────────────────
    {"port": "8020", "method": "POST",   "path": "/telemetry/ingest",              "service": "Telemetry",        "auth": "Bearer", "description": "Ingest robot telemetry batch; body: list[TelemetryRecord]"},
    {"port": "8020", "method": "GET",    "path": "/telemetry/query",               "service": "Telemetry",        "auth": "Bearer", "description": "Time-series query; ?robot_id=&from=&to=&fields="},
    {"port": "8020", "method": "GET",    "path": "/telemetry/anomalies",           "service": "Telemetry",        "auth": "Bearer", "description": "Returns detected anomalies in the last 24h"},
    {"port": "8020", "method": "GET",    "path": "/health",                        "service": "Telemetry",        "auth": "None",   "description": "Service liveness"},

    # ── Billing (8021) ────────────────────────────────────────────────────────
    {"port": "8021", "method": "GET",    "path": "/billing/usage",                 "service": "Billing",          "auth": "Bearer", "description": "GPU-hours consumed this billing cycle per job type"},
    {"port": "8021", "method": "GET",    "path": "/billing/invoices",              "service": "Billing",          "auth": "Bearer", "description": "List past invoices with PDF download URLs"},
    {"port": "8021", "method": "GET",    "path": "/billing/estimate",              "service": "Billing",          "auth": "Bearer", "description": "Estimate cost; ?n_demos=&steps=&gpus="},
    {"port": "8021", "method": "GET",    "path": "/health",                        "service": "Billing",          "auth": "None",   "description": "Service liveness"},

    # ── A/B Testing (8022) ────────────────────────────────────────────────────
    {"port": "8022", "method": "POST",   "path": "/experiments",                   "service": "A/B Testing",      "auth": "Bearer", "description": "Create an A/B experiment; body: {name, checkpoint_a, checkpoint_b, traffic_split}"},
    {"port": "8022", "method": "GET",    "path": "/experiments/{exp_id}/results",  "service": "A/B Testing",      "auth": "Bearer", "description": "Live results with statistical significance p-value"},
    {"port": "8022", "method": "POST",   "path": "/experiments/{exp_id}/conclude", "service": "A/B Testing",      "auth": "Bearer", "description": "Conclude experiment and promote winner to production"},
    {"port": "8022", "method": "GET",    "path": "/health",                        "service": "A/B Testing",      "auth": "None",   "description": "Service liveness"},

    # ── Synthetic Data Generation (8025) ─────────────────────────────────────
    {"port": "8025", "method": "POST",   "path": "/sdg/jobs",                      "service": "SDG",              "auth": "Bearer", "description": "Launch Isaac Sim domain-randomized data generation job"},
    {"port": "8025", "method": "GET",    "path": "/sdg/jobs/{job_id}/status",      "service": "SDG",              "auth": "Bearer", "description": "Poll SDG job state and episodes generated so far"},
    {"port": "8025", "method": "GET",    "path": "/sdg/jobs/{job_id}/results",     "service": "SDG",              "auth": "Bearer", "description": "Returns {dataset_id, n_episodes, total_frames, storage_mb}"},
    {"port": "8025", "method": "GET",    "path": "/sdg/presets",                   "service": "SDG",              "auth": "Bearer", "description": "List available Isaac Sim scene presets and randomization configs"},
    {"port": "8025", "method": "GET",    "path": "/health",                        "service": "SDG",              "auth": "None",   "description": "Service liveness"},

    # ── Safety Monitor (8026) ────────────────────────────────────────────────
    {"port": "8026", "method": "POST",   "path": "/safety/check",                  "service": "Safety Monitor",   "auth": "Bearer", "description": "Run safety policy check on a proposed action chunk before execution"},
    {"port": "8026", "method": "GET",    "path": "/safety/violations",             "service": "Safety Monitor",   "auth": "Bearer", "description": "List safety violations in the last 7 days by severity"},
    {"port": "8026", "method": "GET",    "path": "/health",                        "service": "Safety Monitor",   "auth": "None",   "description": "Service liveness"},

    # ── Documentation (8033, this server) ────────────────────────────────────
    {"port": "8033", "method": "GET",    "path": "/",                              "service": "Docs",             "auth": "None",   "description": "Full SDK documentation portal (HTML)"},
    {"port": "8033", "method": "GET",    "path": "/api/endpoints",                 "service": "Docs",             "auth": "None",   "description": "Complete endpoint catalog as JSON (for SDK auto-discovery)"},
    {"port": "8033", "method": "GET",    "path": "/health",                        "service": "Docs",             "auth": "None",   "description": "Uptime check"},
]

# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="OCI Robot Cloud SDK Docs",
    description="Design-partner reference portal for all OCI Robot Cloud APIs and SDK methods",
    version="1.0.0",
    docs_url="/openapi",
    redoc_url="/redoc",
)

_START_TIME = datetime.now(timezone.utc)

# ── HTML Template ─────────────────────────────────────────────────────────────

def _build_endpoint_rows() -> str:
    rows = []
    for ep in ENDPOINTS:
        method_color = {
            "GET": "#22c55e", "POST": "#3b82f6",
            "DELETE": "#ef4444", "PUT": "#f59e0b", "PATCH": "#a855f7",
        }.get(ep["method"], "#94a3b8")
        auth_badge = (
            '<span class="badge badge-auth">Bearer</span>'
            if ep["auth"] == "Bearer"
            else '<span class="badge badge-none">Open</span>'
        )
        rows.append(
            f'<tr class="ep-row" data-search="{ep["service"].lower()} {ep["method"].lower()} {ep["path"].lower()} {ep["description"].lower()}">'
            f'<td><span class="port">{ep["port"]}</span></td>'
            f'<td><span class="method" style="color:{method_color}">{ep["method"]}</span></td>'
            f'<td><code class="path">{ep["path"]}</code></td>'
            f'<td>{ep["service"]}</td>'
            f'<td>{auth_badge}</td>'
            f'<td class="desc">{ep["description"]}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — SDK Documentation</title>
<style>
  :root {
    --bg:       #1e293b;
    --bg2:      #0f172a;
    --bg3:      #263347;
    --border:   #334155;
    --text:     #e2e8f0;
    --muted:    #94a3b8;
    --red:      #c0392b;
    --red-light:#e74c3c;
    --code-bg:  #0d1b2a;
    --sidebar:  220px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg2);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.6;
  }

  /* ── Header ── */
  header {
    background: var(--bg2);
    border-bottom: 2px solid var(--red);
    padding: 14px 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  header .logo {
    font-size: 18px;
    font-weight: 700;
    color: var(--red-light);
    letter-spacing: .5px;
  }
  header .version {
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    color: var(--muted);
  }
  header .tagline { color: var(--muted); font-size: 13px; margin-left: auto; }

  /* ── Layout ── */
  .layout { display: flex; min-height: calc(100vh - 57px); }

  /* ── Sidebar ── */
  nav {
    width: var(--sidebar);
    flex-shrink: 0;
    background: var(--bg);
    border-right: 1px solid var(--border);
    padding: 24px 0;
    position: sticky;
    top: 57px;
    height: calc(100vh - 57px);
    overflow-y: auto;
  }
  nav a {
    display: block;
    padding: 8px 20px;
    color: var(--muted);
    text-decoration: none;
    font-size: 13px;
    border-left: 3px solid transparent;
    transition: all .15s;
  }
  nav a:hover, nav a.active {
    color: var(--text);
    border-left-color: var(--red-light);
    background: var(--bg3);
  }
  nav .nav-section {
    padding: 16px 20px 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--red-light);
  }

  /* ── Main Content ── */
  main {
    flex: 1;
    padding: 40px 48px;
    max-width: 1100px;
  }

  section { margin-bottom: 72px; }
  h1 { font-size: 28px; font-weight: 700; color: var(--red-light); margin-bottom: 8px; }
  h2 { font-size: 22px; font-weight: 700; color: var(--red-light); margin: 48px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
  h3 { font-size: 16px; font-weight: 600; color: #f1f5f9; margin: 28px 0 10px; }
  h4 { font-size: 13px; font-weight: 600; color: var(--muted); margin: 20px 0 6px; text-transform: uppercase; letter-spacing: .5px; }
  p  { color: var(--muted); margin-bottom: 12px; }

  /* ── Code blocks ── */
  pre {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 20px;
    overflow-x: auto;
    margin: 12px 0 20px;
    font-size: 13px;
    line-height: 1.7;
  }
  code { font-family: "SF Mono", Menlo, "Courier New", monospace; }
  p code, li code, td code {
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 12px;
  }
  .path { color: #7dd3fc; }

  /* ── Method cards ── */
  .method-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 24px;
  }
  .method-card .sig {
    font-family: "SF Mono", monospace;
    font-size: 14px;
    color: #7dd3fc;
    margin-bottom: 10px;
  }
  .method-card .sig .fn-name { color: #fbbf24; }
  .method-card p { margin-bottom: 8px; }
  .params-table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
  .params-table th { text-align: left; color: var(--muted); font-weight: 600; padding: 6px 10px; border-bottom: 1px solid var(--border); }
  .params-table td { padding: 6px 10px; border-bottom: 1px solid #1e2d3d; vertical-align: top; }
  .params-table td:first-child { font-family: monospace; color: #a5f3fc; white-space: nowrap; }
  .params-table td:nth-child(2) { color: #c084fc; white-space: nowrap; }
  .req { color: var(--red-light); font-size: 10px; font-weight: 700; }
  .opt { color: var(--muted); font-size: 10px; }
  .returns { margin-top: 10px; }
  .returns strong { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }

  /* ── Endpoint table ── */
  .search-bar {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 16px;
    color: var(--text);
    font-size: 14px;
    margin-bottom: 16px;
    outline: none;
  }
  .search-bar:focus { border-color: var(--red-light); }
  .ep-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .ep-table th {
    text-align: left;
    padding: 10px 12px;
    color: var(--muted);
    font-weight: 600;
    background: var(--bg);
    border-bottom: 2px solid var(--border);
    position: sticky;
    top: 0;
  }
  .ep-table td { padding: 9px 12px; border-bottom: 1px solid #1a2535; vertical-align: middle; }
  .ep-table tr:hover td { background: var(--bg3); }
  .port { color: var(--muted); font-family: monospace; font-size: 12px; }
  .method { font-family: monospace; font-weight: 700; font-size: 12px; }
  .badge { display: inline-block; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: 600; }
  .badge-auth { background: #1e3a5f; color: #7dd3fc; }
  .badge-none { background: #1a2e1a; color: #86efac; }
  .desc { color: var(--muted); }
  .no-results { color: var(--muted); padding: 24px; text-align: center; display: none; }

  /* ── Schema blocks ── */
  .schema-block {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 20px;
    font-family: monospace;
    font-size: 13px;
    line-height: 1.8;
    margin: 12px 0 20px;
    overflow-x: auto;
  }
  .k  { color: #7dd3fc; }   /* key   */
  .t  { color: #c084fc; }   /* type  */
  .cm { color: #475569; }   /* comment */
  .s  { color: #86efac; }   /* string value */
  .n  { color: #fbbf24; }   /* number value */

  /* ── Alerts ── */
  .note {
    background: #1e2d3d;
    border-left: 3px solid #3b82f6;
    border-radius: 0 6px 6px 0;
    padding: 12px 16px;
    margin: 12px 0 20px;
    color: var(--muted);
    font-size: 13px;
  }
  .note strong { color: #7dd3fc; }

  /* ── CLI table ── */
  .cli-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 20px; }
  .cli-table th { text-align: left; padding: 8px 12px; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--border); }
  .cli-table td { padding: 8px 12px; border-bottom: 1px solid #1a2535; vertical-align: top; }
  .cli-table td:first-child { font-family: monospace; color: #fbbf24; white-space: nowrap; }
  .cli-table td:nth-child(2) { font-family: monospace; color: #a5f3fc; font-size: 12px; }

  /* ── Example tabs ── */
  .ex-tab-bar { display: flex; gap: 4px; margin-bottom: -1px; }
  .ex-tab {
    padding: 8px 18px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    cursor: pointer;
    color: var(--muted);
    font-size: 13px;
    font-weight: 500;
  }
  .ex-tab.active { background: var(--code-bg); color: var(--text); border-color: var(--border); }
  .ex-panel { display: none; }
  .ex-panel.active { display: block; }

  ul { color: var(--muted); padding-left: 20px; }
  li { margin-bottom: 4px; }
  a { color: #7dd3fc; }
</style>
</head>
<body>

<header>
  <div class="logo">OCI Robot Cloud</div>
  <span class="version">SDK v1.0 · API 2026-Q1</span>
  <span class="tagline">Design Partner Reference &nbsp;·&nbsp; Confidential</span>
</header>

<div class="layout">

<!-- ── Sidebar ── -->
<nav id="sidebar">
  <div class="nav-section">Reference</div>
  <a href="#python-sdk">Python SDK</a>
  <a href="#rest-api">REST API</a>
  <a href="#cli">CLI Reference</a>
  <a href="#data-formats">Data Formats</a>
  <a href="#examples">Examples</a>
  <div class="nav-section">Meta</div>
  <a href="#auth">Authentication</a>
  <a href="#errors">Error Codes</a>
  <a href="/api/endpoints">Endpoint JSON ↗</a>
  <a href="/openapi">OpenAPI ↗</a>
  <a href="/health">Health ↗</a>
</nav>

<!-- ── Main ── -->
<main>

<!-- ════════════════════════════════════════════════════════════ OVERVIEW -->
<section id="overview">
  <h1>OCI Robot Cloud SDK</h1>
  <p>
    Complete reference for the OCI Robot Cloud Python SDK, REST APIs, CLI, data formats,
    and runnable examples. This portal is auto-generated from the internal endpoint catalog
    and is served from <code>localhost:8033</code>.
  </p>
  <p>
    Services run across ports <strong>8001–8050</strong> on the OCI compute instance.
    All write endpoints require a <code>Bearer</code> token obtained from the
    <a href="#auth">Authentication</a> section.
  </p>
</section>

<!-- ════════════════════════════════════════════════════════ PYTHON SDK -->
<section id="python-sdk">
<h2>Python SDK</h2>
<p>Install via pip from the private OCI artifact registry:</p>
<pre><code>pip install oci-robot-cloud
# or from source:
pip install git+https://github.com/qianjun22/roboticsai.git#subdirectory=sdk</code></pre>

<p>All SDK operations go through <code>RobotCloudClient</code>:</p>
<pre><code>from oci_robot_cloud import RobotCloudClient

client = RobotCloudClient(
    base_url="http://&lt;OCI_IP&gt;:8080",
    api_key="rc_live_••••••••",   # from portal
    timeout=120,
)</code></pre>

<!-- train -->
<div class="method-card">
  <div class="sig"><span class="fn-name">client.train</span>(dataset_id, steps, learning_rate, embodiment, tag)</div>
  <p>Submit a fine-tuning job on an uploaded dataset. Returns immediately; poll with <code>status()</code>.</p>
  <table class="params-table">
    <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
    <tr><td>dataset_id</td><td>str</td><td><span class="req">required</span></td><td>ID returned by the Data Collection API</td></tr>
    <tr><td>steps</td><td>int</td><td><span class="req">required</span></td><td>Training steps (recommended: 1 000–10 000)</td></tr>
    <tr><td>learning_rate</td><td>float</td><td><span class="opt">optional</span></td><td>Default: <code>1e-4</code></td></tr>
    <tr><td>embodiment</td><td>str</td><td><span class="opt">optional</span></td><td><code>"franka"</code> | <code>"ur5"</code> | <code>"generic_6dof"</code>. Default: <code>"franka"</code></td></tr>
    <tr><td>tag</td><td>str</td><td><span class="opt">optional</span></td><td>Human-readable label for the run</td></tr>
  </table>
  <div class="returns"><strong>Returns</strong> <code>TrainJob</code></div>
<pre><code>job = client.train(
    dataset_id="ds_abc123",
    steps=5000,
    learning_rate=1e-4,
    embodiment="franka",
    tag="pick-and-place-v2",
)
print(job.job_id)   # "job_7f3a..."</code></pre>
</div>

<!-- status -->
<div class="method-card">
  <div class="sig"><span class="fn-name">client.status</span>(job_id)</div>
  <p>Poll a training or evaluation job. Returns a <code>JobStatus</code> object.</p>
  <table class="params-table">
    <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
    <tr><td>job_id</td><td>str</td><td><span class="req">required</span></td><td>Job ID from <code>train()</code>, <code>eval()</code>, or <code>sdg()</code></td></tr>
  </table>
  <div class="returns"><strong>Returns</strong> <code>JobStatus(job_id, state, progress_pct, eta_s, message)</code></div>
<pre><code>import time

while True:
    s = client.status(job.job_id)
    print(f"{s.state}  {s.progress_pct:.0f}%  eta={s.eta_s}s")
    if s.state in ("done", "failed"):
        break
    time.sleep(10)</code></pre>
</div>

<!-- results / inspect -->
<div class="method-card">
  <div class="sig"><span class="fn-name">client.inspect</span>(job_id)</div>
  <p>Retrieve full results for a completed training or evaluation job.</p>
  <table class="params-table">
    <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
    <tr><td>job_id</td><td>str</td><td><span class="req">required</span></td><td>Completed job ID</td></tr>
  </table>
  <div class="returns"><strong>Returns</strong> <code>TrainResult(mae, final_loss, checkpoint_id, cost_usd, duration_s, logs_url)</code></div>
<pre><code>result = client.inspect(job.job_id)
print(f"MAE={result.mae:.4f}  loss={result.final_loss:.4f}")
print(f"checkpoint: {result.checkpoint_id}")
print(f"cost: ${result.cost_usd:.4f}")</code></pre>
</div>

<!-- deploy -->
<div class="method-card">
  <div class="sig"><span class="fn-name">client.deploy</span>(checkpoint_id, target, output_path)</div>
  <p>Package a checkpoint as a Jetson-ready tarball or OCI container image.</p>
  <table class="params-table">
    <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
    <tr><td>checkpoint_id</td><td>str</td><td><span class="req">required</span></td><td>Checkpoint ID from <code>inspect()</code></td></tr>
    <tr><td>target</td><td>str</td><td><span class="opt">optional</span></td><td><code>"jetson_orin"</code> | <code>"oci_container"</code>. Default: <code>"jetson_orin"</code></td></tr>
    <tr><td>output_path</td><td>str</td><td><span class="opt">optional</span></td><td>Local path to write the tarball. If omitted, returns a signed download URL.</td></tr>
  </table>
  <div class="returns"><strong>Returns</strong> <code>DeployResult(download_url, size_mb, sha256, expires_at)</code></div>
<pre><code>deploy = client.deploy(result.checkpoint_id, target="jetson_orin")
print(deploy.download_url)
# download and scp to robot
import urllib.request
urllib.request.urlretrieve(deploy.download_url, "/tmp/model.tar.gz")</code></pre>
</div>

<!-- pricing -->
<div class="method-card">
  <div class="sig"><span class="fn-name">client.pricing</span>(n_demos, steps, gpus)</div>
  <p>Estimate training cost before submitting a job. Does not create any resources.</p>
  <table class="params-table">
    <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Description</th></tr>
    <tr><td>n_demos</td><td>int</td><td><span class="req">required</span></td><td>Number of demonstration episodes in dataset</td></tr>
    <tr><td>steps</td><td>int</td><td><span class="req">required</span></td><td>Planned training steps</td></tr>
    <tr><td>gpus</td><td>int</td><td><span class="opt">optional</span></td><td>Number of A100s (1 or 4). Default: <code>1</code></td></tr>
  </table>
  <div class="returns"><strong>Returns</strong> <code>PriceEstimate(gpu_hours, cost_usd, throughput_it_s, eta_minutes)</code></div>
<pre><code>est = client.pricing(n_demos=1000, steps=5000, gpus=1)
print(f"~${est.cost_usd:.2f}  ({est.eta_minutes:.0f} min)")
# ~$0.21  (58 min)</code></pre>
</div>

</section>

<!-- ═══════════════════════════════════════════════════════════ REST API -->
<section id="rest-api">
<h2>REST API</h2>
<p>
  All endpoints accept and return <code>application/json</code> unless noted.
  Authenticated endpoints require <code>Authorization: Bearer &lt;token&gt;</code>.
  See <a href="#auth">Authentication</a> for token acquisition.
</p>

<input
  id="ep-search"
  class="search-bar"
  type="text"
  placeholder="Search endpoints — try 'POST', 'train', '8003', 'eval'…"
  oninput="filterEndpoints(this.value)"
/>

<div style="overflow-x:auto">
<table class="ep-table" id="ep-table">
  <thead>
    <tr>
      <th>Port</th>
      <th>Method</th>
      <th>Path</th>
      <th>Service</th>
      <th>Auth</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody id="ep-tbody">
    ENDPOINT_ROWS
  </tbody>
</table>
<div class="no-results" id="no-results">No endpoints match your search.</div>
</div>
</section>

<!-- ════════════════════════════════════════════════════════ CLI REFERENCE -->
<section id="cli">
<h2>CLI Reference</h2>
<p>Install the CLI alongside the Python package:</p>
<pre><code>pip install oci-robot-cloud
oci-robot-cloud --version  # 1.0.0</code></pre>

<p>Configure credentials once:</p>
<pre><code>oci-robot-cloud configure
# OCI Robot Cloud host [http://localhost:8080]: http://&lt;OCI_IP&gt;:8080
# API key: rc_live_••••••••
# Config saved to ~/.oci-robot-cloud/config.json</code></pre>

<h3>Commands</h3>
<table class="cli-table">
  <tr><th>Command</th><th>Flags</th><th>Description</th></tr>
  <tr>
    <td>train</td>
    <td>--dataset &lt;id&gt; --steps &lt;n&gt; [--lr &lt;f&gt;] [--embodiment &lt;e&gt;] [--tag &lt;s&gt;] [--wait]</td>
    <td>Submit a fine-tuning job. <code>--wait</code> blocks until completion and prints results.</td>
  </tr>
  <tr>
    <td>status</td>
    <td>--job &lt;id&gt; [--watch]</td>
    <td>Show job state. <code>--watch</code> refreshes every 10 s until terminal state.</td>
  </tr>
  <tr>
    <td>results</td>
    <td>--job &lt;id&gt;</td>
    <td>Print training results (MAE, loss, cost, checkpoint ID).</td>
  </tr>
  <tr>
    <td>deploy</td>
    <td>--checkpoint &lt;id&gt; [--target jetson_orin|oci_container] [--out &lt;path&gt;]</td>
    <td>Package checkpoint for deployment. Downloads tarball if <code>--out</code> given.</td>
  </tr>
  <tr>
    <td>eval</td>
    <td>--checkpoint &lt;id&gt; --suite &lt;name&gt; [--n-eps 20] [--wait]</td>
    <td>Run LIBERO evaluation suite against a checkpoint.</td>
  </tr>
  <tr>
    <td>upload</td>
    <td>--path &lt;dir&gt; [--dataset &lt;name&gt;] [--embodiment &lt;e&gt;]</td>
    <td>Upload a local LeRobot v2 episode directory and create a dataset.</td>
  </tr>
  <tr>
    <td>datasets list</td>
    <td>[--json]</td>
    <td>List datasets with episode counts, size, and creation date.</td>
  </tr>
  <tr>
    <td>jobs list</td>
    <td>[--limit 20] [--json]</td>
    <td>List recent jobs with state and cost.</td>
  </tr>
  <tr>
    <td>pricing</td>
    <td>--demos &lt;n&gt; --steps &lt;n&gt; [--gpus 1|4]</td>
    <td>Print cost estimate without creating a job.</td>
  </tr>
  <tr>
    <td>dagger run</td>
    <td>--checkpoint &lt;id&gt; --rollouts &lt;n&gt; [--mix-ratio 0.5] [--iters 5]</td>
    <td>Run DAgger improvement loop against the LIBERO simulator.</td>
  </tr>
  <tr>
    <td>sdg generate</td>
    <td>--preset &lt;name&gt; --n-eps &lt;n&gt; [--randomize-lighting] [--randomize-textures]</td>
    <td>Generate synthetic training data via Isaac Sim (OCI-only).</td>
  </tr>
  <tr>
    <td>configure</td>
    <td>[--reset]</td>
    <td>Set or reset API host and credentials.</td>
  </tr>
</table>

<h3>Examples</h3>
<pre><code># Upload 200 episodes and train 5 000 steps, wait for completion
oci-robot-cloud upload --path ./my_demos/ --dataset "pick-v1"
oci-robot-cloud train --dataset pick-v1 --steps 5000 --wait

# Check status of a specific job
oci-robot-cloud status --job job_7f3a2b1c --watch

# Price check for a large run
oci-robot-cloud pricing --demos 2000 --steps 10000 --gpus 4

# Deploy best checkpoint to Jetson
oci-robot-cloud deploy --checkpoint ckpt_9e4d --out ~/robot_model.tar.gz

# Full DAgger loop (3 iterations, 50 rollouts each)
oci-robot-cloud dagger run --checkpoint ckpt_9e4d --rollouts 50 --iters 3</code></pre>
</section>

<!-- ═══════════════════════════════════════════════════════ DATA FORMATS -->
<section id="data-formats">
<h2>Data Formats</h2>

<h3>LeRobot v2 Episode Format</h3>
<p>
  The upload API expects episodes in LeRobot v2 format — a directory of Parquet files
  plus a metadata JSON. Each episode is one continuous robot trajectory.
</p>
<pre><code>my_dataset/
  meta/
    info.json            # dataset-level metadata
    tasks.jsonl          # task descriptions
    episodes.jsonl       # episode manifest
  data/
    chunk-000/
      episode_000000.parquet
      episode_000001.parquet
      ...
  videos/
    chunk-000/
      observation.images.top/
        episode_000000.mp4
        ...</code></pre>

<h4>info.json schema</h4>
<div class="schema-block">
<span class="k">"codebase_version"</span>: <span class="s">"v2.0"</span>,<br>
<span class="k">"robot_type"</span>:        <span class="s">"franka"</span>,   <span class="cm">// franka | ur5 | generic_6dof</span><br>
<span class="k">"fps"</span>:               <span class="n">10</span>,<br>
<span class="k">"features"</span>: {<br>
&nbsp;&nbsp;<span class="k">"observation.state"</span>: { <span class="k">"dtype"</span>: <span class="s">"float32"</span>, <span class="k">"shape"</span>: [<span class="n">7</span>]  },  <span class="cm">// 7-DOF joint angles</span><br>
&nbsp;&nbsp;<span class="k">"action"</span>:             { <span class="k">"dtype"</span>: <span class="s">"float32"</span>, <span class="k">"shape"</span>: [<span class="n">7</span>]  },  <span class="cm">// delta joint actions</span><br>
&nbsp;&nbsp;<span class="k">"observation.images.top"</span>: { <span class="k">"dtype"</span>: <span class="s">"video"</span>, <span class="k">"shape"</span>: [<span class="n">3</span>, <span class="n">480</span>, <span class="n">640</span>] }<br>
},<br>
<span class="k">"splits"</span>: { <span class="k">"train"</span>: <span class="s">"0:950"</span>, <span class="k">"test"</span>: <span class="s">"950:1000"</span> },<br>
<span class="k">"total_episodes"</span>: <span class="n">1000</span>,<br>
<span class="k">"total_frames"</span>:   <span class="n">87340</span>
</div>

<h4>episode Parquet columns</h4>
<table class="params-table" style="margin-top:8px">
  <tr><th>Column</th><th>Type</th><th>Shape</th><th>Description</th></tr>
  <tr><td>observation.state</td><td>float32</td><td>[7]</td><td>Joint positions (rad) at each timestep</td></tr>
  <tr><td>action</td><td>float32</td><td>[7]</td><td>Delta joint commands applied at this step</td></tr>
  <tr><td>timestamp</td><td>float64</td><td>scalar</td><td>Seconds since episode start</td></tr>
  <tr><td>frame_index</td><td>int64</td><td>scalar</td><td>Frame number within episode</td></tr>
  <tr><td>episode_index</td><td>int64</td><td>scalar</td><td>Episode index within dataset</td></tr>
  <tr><td>next.done</td><td>bool</td><td>scalar</td><td><code>True</code> on final frame of episode</td></tr>
  <tr><td>task_index</td><td>int64</td><td>scalar</td><td>Index into <code>tasks.jsonl</code></td></tr>
</table>

<div class="note">
  <strong>Minimum episode length:</strong> The fine-tune pipeline rejects episodes with
  fewer than <code>10 frames</code> (hard filter in DAgger data collection). Typical
  episode length is 50–200 frames.
</div>

<h3>Checkpoint Structure</h3>
<pre><code>checkpoint_ckpt_9e4d/
  config.json          # training config snapshot
  model.safetensors    # GR00T N1.6 weights (6.7 GB)
  embodiment.json      # embodiment adapter config
  training_stats.json  # loss curve, MAE per epoch
  modality_config.py   # sensor/action space definition</code></pre>

<h4>training_stats.json schema</h4>
<div class="schema-block">
{<br>
&nbsp;&nbsp;<span class="k">"job_id"</span>:         <span class="s">"job_7f3a2b1c"</span>,<br>
&nbsp;&nbsp;<span class="k">"checkpoint_id"</span>: <span class="s">"ckpt_9e4d"</span>,<br>
&nbsp;&nbsp;<span class="k">"steps"</span>:         <span class="n">5000</span>,<br>
&nbsp;&nbsp;<span class="k">"final_loss"</span>:    <span class="n">0.099</span>,<br>
&nbsp;&nbsp;<span class="k">"mae"</span>:           <span class="n">0.013</span>,<br>
&nbsp;&nbsp;<span class="k">"duration_s"</span>:    <span class="n">2124</span>,<br>
&nbsp;&nbsp;<span class="k">"cost_usd"</span>:      <span class="n">2.12</span>,<br>
&nbsp;&nbsp;<span class="k">"loss_curve"</span>:    [<span class="n">0.847</span>, <span class="n">0.412</span>, <span class="n">0.231</span>, <span class="n">0.148</span>, <span class="n">0.099</span>],  <span class="cm">// per 1k steps</span><br>
&nbsp;&nbsp;<span class="k">"throughput_it_s"</span>: <span class="n">2.35</span>,<br>
&nbsp;&nbsp;<span class="k">"created_at"</span>:   <span class="s">"2026-03-29T04:12:00Z"</span><br>
}
</div>

<h3>Evaluation Result JSON</h3>
<p>Returned by <code>GET /eval/{eval_id}/results</code> and saved to disk after each eval run.</p>
<div class="schema-block">
{<br>
&nbsp;&nbsp;<span class="k">"eval_id"</span>:       <span class="s">"eval_cc3d"</span>,<br>
&nbsp;&nbsp;<span class="k">"checkpoint_id"</span>: <span class="s">"ckpt_9e4d"</span>,<br>
&nbsp;&nbsp;<span class="k">"task_suite"</span>:    <span class="s">"LIBERO_SPATIAL"</span>,<br>
&nbsp;&nbsp;<span class="k">"n_episodes"</span>:    <span class="n">20</span>,<br>
&nbsp;&nbsp;<span class="k">"success_rate"</span>:  <span class="n">0.75</span>,<br>
&nbsp;&nbsp;<span class="k">"mean_reward"</span>:   <span class="n">0.68</span>,<br>
&nbsp;&nbsp;<span class="k">"mean_latency_ms"</span>: <span class="n">231</span>,<br>
&nbsp;&nbsp;<span class="k">"per_task"</span>: {<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span class="s">"pick_up_the_black_bowl"</span>:    { <span class="k">"success"</span>: <span class="n">0.85</span>, <span class="k">"mean_reward"</span>: <span class="n">0.79</span> },<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span class="s">"stack_the_blocks"</span>:          { <span class="k">"success"</span>: <span class="n">0.70</span>, <span class="k">"mean_reward"</span>: <span class="n">0.64</span> },<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span class="s">"place_in_bin"</span>:              { <span class="k">"success"</span>: <span class="n">0.80</span>, <span class="k">"mean_reward"</span>: <span class="n">0.72</span> }<br>
&nbsp;&nbsp;},<br>
&nbsp;&nbsp;<span class="k">"video_url"</span>:      <span class="s">"https://&lt;oci-bucket&gt;/evals/eval_cc3d.mp4"</span>,<br>
&nbsp;&nbsp;<span class="k">"created_at"</span>:    <span class="s">"2026-03-29T06:00:00Z"</span><br>
}
</div>
</section>

<!-- ════════════════════════════════════════════════════════════ EXAMPLES -->
<section id="examples">
<h2>Examples</h2>

<div class="ex-tab-bar">
  <button class="ex-tab active" onclick="showExample(0)">Quickstart</button>
  <button class="ex-tab"        onclick="showExample(1)">DAgger Loop</button>
  <button class="ex-tab"        onclick="showExample(2)">Cross-Embodiment</button>
</div>

<!-- Quickstart -->
<div class="ex-panel active" id="ex-0">
<pre><code>&#34;&#34;&#34;
Quickstart: Upload demos, train 1 000 steps, evaluate.
Runtime on 1x A100: ~25 min, ~$0.045
&#34;&#34;&#34;
from pathlib import Path
from oci_robot_cloud import RobotCloudClient
import time

client = RobotCloudClient(
    base_url="http://&lt;OCI_IP&gt;:8080",
    api_key="rc_live_••••••••",
)

# ── 1. Upload demo episodes ────────────────────────────────────────────────
print("Uploading episodes...")
dataset = client.upload_dataset(
    path=Path("./my_demos"),      # LeRobot v2 directory
    name="quickstart-pick-v1",
    embodiment="franka",
)
print(f"Dataset: {dataset.dataset_id}  ({dataset.n_episodes} episodes)")

# ── 2. Estimate cost ───────────────────────────────────────────────────────
est = client.pricing(n_demos=dataset.n_episodes, steps=1000)
print(f"Estimated cost: ${est.cost_usd:.3f}  (~{est.eta_minutes:.0f} min)")

# ── 3. Submit training job ─────────────────────────────────────────────────
job = client.train(
    dataset_id=dataset.dataset_id,
    steps=1000,
    tag="quickstart",
)
print(f"Job submitted: {job.job_id}")

# ── 4. Poll until done ────────────────────────────────────────────────────
while True:
    s = client.status(job.job_id)
    print(f"  {s.state}  {s.progress_pct:.0f}%")
    if s.state == "done":
        break
    elif s.state == "failed":
        raise RuntimeError(f"Training failed: {s.message}")
    time.sleep(15)

# ── 5. Inspect results ────────────────────────────────────────────────────
result = client.inspect(job.job_id)
print(f"MAE={result.mae:.4f}  loss={result.final_loss:.4f}")
print(f"Checkpoint: {result.checkpoint_id}")
print(f"Cost: ${result.cost_usd:.4f}")

# ── 6. Run evaluation ─────────────────────────────────────────────────────
eval_job = client.eval(
    checkpoint_id=result.checkpoint_id,
    task_suite="LIBERO_SPATIAL",
    n_episodes=20,
)
while True:
    es = client.status(eval_job.eval_id)
    if es.state == "done":
        break
    time.sleep(10)

ev = client.inspect(eval_job.eval_id)
print(f"Success rate: {ev.success_rate:.0%}")

# ── 7. Deploy to Jetson ───────────────────────────────────────────────────
deploy = client.deploy(result.checkpoint_id, target="jetson_orin")
print(f"Download: {deploy.download_url}")</code></pre>
</div>

<!-- DAgger Loop -->
<div class="ex-panel" id="ex-1">
<pre><code>&#34;&#34;&#34;
DAgger iterative improvement loop.
Each iteration: rollout policy → collect corrections → retrain → evaluate.
Expected improvement: +5–15% success rate per iteration.
&#34;&#34;&#34;
from oci_robot_cloud import RobotCloudClient
import time

client = RobotCloudClient(base_url="http://&lt;OCI_IP&gt;:8080", api_key="rc_live_••••••••")
client_dagger = RobotCloudClient(base_url="http://&lt;OCI_IP&gt;:8015", api_key="rc_live_••••••••")

BASE_CHECKPOINT = "ckpt_9e4d"   # from initial training run
N_ITERATIONS    = 5
N_ROLLOUTS      = 50            # simulator episodes per iteration
MIX_RATIO       = 0.5           # fraction of correction data vs original

current_checkpoint = BASE_CHECKPOINT
history = []

for i in range(N_ITERATIONS):
    print(f"\\n=== DAgger Iteration {i+1}/{N_ITERATIONS} ===")

    # launch DAgger run (rollouts + fine-tune)
    run = client_dagger.post("/dagger/runs", json={
        "base_checkpoint_id": current_checkpoint,
        "n_rollouts":         N_ROLLOUTS,
        "mix_ratio":          MIX_RATIO,
    })
    run_id = run["run_id"]
    print(f"  Run ID: {run_id}")

    # wait for iteration to complete
    while True:
        s = client_dagger.get(f"/dagger/runs/{run_id}/status")
        print(f"  {s['state']}  iteration {s['current_iteration']}")
        if s["state"] in ("done", "failed"):
            break
        time.sleep(30)

    if s["state"] == "failed":
        print("  DAgger run failed, stopping.")
        break

    # get new checkpoint from this iteration
    history_data = client_dagger.get(f"/dagger/runs/{run_id}/history")
    latest = history_data["iterations"][-1]
    current_checkpoint = latest["checkpoint_id"]
    history.append(latest)
    print(f"  New checkpoint: {current_checkpoint}")
    print(f"  Success rate: {latest['success_rate']:.0%}")

# evaluate final checkpoint
print("\\n=== Final Evaluation ===")
eval_job = client.eval(
    checkpoint_id=current_checkpoint,
    task_suite="LIBERO_SPATIAL",
    n_episodes=50,
)
while True:
    es = client.status(eval_job.eval_id)
    if es.state == "done":
        break
    time.sleep(10)
ev = client.inspect(eval_job.eval_id)
print(f"Final success rate: {ev.success_rate:.0%}")
print("DAgger history:", [(h["iteration"], f"{h['success_rate']:.0%}") for h in history])</code></pre>
</div>

<!-- Cross-Embodiment -->
<div class="ex-panel" id="ex-2">
<pre><code>&#34;&#34;&#34;
Cross-embodiment fine-tune: start from a Franka checkpoint, adapt to UR5.
Uses the embodiment adapter to transfer manipulation skills across arm morphologies.
Expected: 60-70% of Franka performance with only 100 UR5 demos (vs 1000 from scratch).
&#34;&#34;&#34;
from oci_robot_cloud import RobotCloudClient
from pathlib import Path
import time

client = RobotCloudClient(base_url="http://&lt;OCI_IP&gt;:8080", api_key="rc_live_••••••••")

# ── 1. Upload UR5 adaptation demos (small set) ─────────────────────────────
ur5_dataset = client.upload_dataset(
    path=Path("./ur5_adaptation_demos"),   # 100 UR5 episodes
    name="ur5-adapt-v1",
    embodiment="ur5",
)
print(f"UR5 dataset: {ur5_dataset.dataset_id} ({ur5_dataset.n_episodes} episodes)")

# ── 2. Submit cross-embodiment fine-tune ──────────────────────────────────
# Pass source_checkpoint to initialise from Franka weights.
# The platform automatically activates the embodiment adapter layer.
job = client.train(
    dataset_id=ur5_dataset.dataset_id,
    steps=2000,
    embodiment="ur5",
    learning_rate=5e-5,          # lower LR for adapter-only fine-tune
    tag="franka-to-ur5-xemb",
    extra={
        "source_checkpoint": "ckpt_9e4d",   # Franka base
        "freeze_backbone":   True,           # only train adapter
    },
)
print(f"Cross-embodiment job: {job.job_id}")

# ── 3. Wait ───────────────────────────────────────────────────────────────
while True:
    s = client.status(job.job_id)
    if s.state == "done":
        break
    elif s.state == "failed":
        raise RuntimeError(s.message)
    print(f"  {s.state}  {s.progress_pct:.0f}%")
    time.sleep(15)

result = client.inspect(job.job_id)
print(f"UR5 MAE:  {result.mae:.4f}   (Franka baseline 0.013)")
print(f"Checkpoint: {result.checkpoint_id}")

# ── 4. Evaluate on UR5 task suite ─────────────────────────────────────────
eval_job = client.eval(
    checkpoint_id=result.checkpoint_id,
    task_suite="LIBERO_OBJECT",
    n_episodes=20,
)
while True:
    es = client.status(eval_job.eval_id)
    if es.state == "done":
        break
    time.sleep(10)
ev = client.inspect(eval_job.eval_id)
print(f"UR5 success rate: {ev.success_rate:.0%}")

# ── 5. Deploy UR5 model ───────────────────────────────────────────────────
deploy = client.deploy(result.checkpoint_id, target="jetson_orin")
print(f"UR5 model ready: {deploy.download_url}")</code></pre>
</div>
</section>

<!-- ════════════════════════════════════════════════════════ AUTHENTICATION -->
<section id="auth">
<h2>Authentication</h2>
<p>
  OCI Robot Cloud uses static API keys for design-partner access. Keys are prefixed
  <code>rc_live_</code> for production and <code>rc_test_</code> for the sandbox environment.
</p>
<pre><code># HTTP header
Authorization: Bearer rc_live_••••••••••••••••

# Python SDK
client = RobotCloudClient(api_key="rc_live_••••••••••••••••")

# CLI
oci-robot-cloud configure
# enter your key when prompted</code></pre>
<p>Contact your OCI Robot Cloud account manager to provision or rotate keys.</p>
</section>

<!-- ═══════════════════════════════════════════════════════════ ERROR CODES -->
<section id="errors">
<h2>Error Codes</h2>
<table class="params-table">
  <tr><th>HTTP Status</th><th>Code</th><th>Meaning</th></tr>
  <tr><td>400</td><td>INVALID_REQUEST</td><td>Missing or malformed request body field</td></tr>
  <tr><td>401</td><td>UNAUTHORIZED</td><td>Missing or invalid Bearer token</td></tr>
  <tr><td>403</td><td>FORBIDDEN</td><td>Token does not have permission for this resource</td></tr>
  <tr><td>404</td><td>NOT_FOUND</td><td>Job ID, dataset ID, or checkpoint ID does not exist</td></tr>
  <tr><td>409</td><td>CONFLICT</td><td>Resource already exists (e.g. duplicate dataset name)</td></tr>
  <tr><td>422</td><td>VALIDATION_ERROR</td><td>Pydantic validation failure — see <code>detail</code> array</td></tr>
  <tr><td>429</td><td>RATE_LIMITED</td><td>Too many requests; back off and retry after <code>Retry-After</code> seconds</td></tr>
  <tr><td>500</td><td>INTERNAL_ERROR</td><td>Unexpected server error; contact support with the <code>request_id</code></td></tr>
  <tr><td>503</td><td>GPU_UNAVAILABLE</td><td>No A100 capacity available; job queued automatically</td></tr>
</table>
<p>All error responses include:</p>
<div class="schema-block">
{ <span class="k">"error"</span>: <span class="s">"NOT_FOUND"</span>, <span class="k">"message"</span>: <span class="s">"Job job_xyz not found"</span>, <span class="k">"request_id"</span>: <span class="s">"req_abc"</span> }
</div>
</section>

</main>
</div><!-- .layout -->

<script>
// ── Search ──────────────────────────────────────────────────────────────────
function filterEndpoints(q) {
  const rows = document.querySelectorAll('#ep-tbody .ep-row');
  const term = q.toLowerCase().trim();
  let visible = 0;
  rows.forEach(row => {
    const haystack = row.dataset.search || '';
    const match = !term || haystack.includes(term);
    row.style.display = match ? '' : 'none';
    if (match) visible++;
  });
  document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}

// ── Example tabs ─────────────────────────────────────────────────────────────
function showExample(idx) {
  document.querySelectorAll('.ex-panel').forEach((p, i) => {
    p.classList.toggle('active', i === idx);
  });
  document.querySelectorAll('.ex-tab').forEach((t, i) => {
    t.classList.toggle('active', i === idx);
  });
}

// ── Active nav link on scroll ─────────────────────────────────────────────────
const sections = document.querySelectorAll('section[id]');
const navLinks  = document.querySelectorAll('nav a[href^="#"]');

function updateNav() {
  let current = '';
  sections.forEach(sec => {
    if (window.scrollY >= sec.offsetTop - 80) current = sec.id;
  });
  navLinks.forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === '#' + current);
  });
}
window.addEventListener('scroll', updateNav, { passive: true });
updateNav();
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> HTMLResponse:
    """Render the full SDK documentation portal."""
    rows = _build_endpoint_rows()
    html = _HTML.replace("ENDPOINT_ROWS", rows)
    return HTMLResponse(content=html)


@app.get("/api/endpoints", summary="Full endpoint catalog (JSON)", tags=["Meta"])
async def api_endpoints() -> JSONResponse:
    """
    Returns the complete endpoint catalog as JSON.
    Intended for SDK auto-discovery and tooling that needs to enumerate services.
    """
    return JSONResponse(content={
        "version": "2026-Q1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(ENDPOINTS),
        "endpoints": ENDPOINTS,
    })


@app.get("/health", summary="Uptime check", tags=["Meta"])
async def health() -> dict[str, Any]:
    """Liveness probe for the documentation server."""
    uptime = (datetime.now(timezone.utc) - _START_TIME).total_seconds()
    return {
        "status": "ok",
        "service": "sdk_documentation_server",
        "port": 8033,
        "uptime_s": round(uptime, 1),
        "endpoint_count": len(ENDPOINTS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCI Robot Cloud SDK Documentation Portal")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8033, help="Port (default: 8033)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print(f"OCI Robot Cloud SDK Docs  →  http://{args.host}:{args.port}")
    print(f"Endpoint catalog JSON     →  http://{args.host}:{args.port}/api/endpoints")
    print(f"OpenAPI UI                →  http://{args.host}:{args.port}/openapi")
    uvicorn.run(
        "sdk_documentation_server:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
