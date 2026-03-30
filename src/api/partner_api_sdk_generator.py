#!/usr/bin/env python3
"""
partner_api_sdk_generator.py — OCI Robot Cloud Partner SDK & Documentation Generator

Generates partner-specific Python SDK snippets and HTML quickstart docs for the
OCI Robot Cloud API. Each partner tier (pilot / growth / enterprise) unlocks a
different subset of endpoints. Output is one HTML file per partner plus a
combined index.html.

Usage:
    python partner_api_sdk_generator.py [--partner NAME] [--output-dir DIR]
"""

import argparse
import json
import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PartnerConfig:
    partner_name: str
    tier: str                        # "pilot" | "growth" | "enterprise"
    api_key: str
    base_url: str
    assigned_ports: List[int]
    enabled_endpoints: List[str]


@dataclass
class APIEndpoint:
    name: str
    method: str
    path: str
    description: str
    params: Dict
    example_response: Dict


# ---------------------------------------------------------------------------
# Endpoint catalog (12 endpoints)
# ---------------------------------------------------------------------------

ENDPOINTS: List[APIEndpoint] = [
    APIEndpoint(
        name="health",
        method="GET",
        path="/v1/health",
        description="Check API health and service availability.",
        params={},
        example_response={"status": "ok", "version": "1.4.0", "uptime_seconds": 3600},
    ),
    APIEndpoint(
        name="list_tasks",
        method="GET",
        path="/v1/tasks",
        description="List available robot manipulation tasks in the catalog.",
        params={"limit": "int (default 20)", "offset": "int (default 0)"},
        example_response={"tasks": ["pick_and_place", "drawer_open", "peg_insert"], "total": 42},
    ),
    APIEndpoint(
        name="upload_demos",
        method="POST",
        path="/v1/demos/upload",
        description="Upload a batch of demonstration episodes for a given task.",
        params={"task_name": "str", "demos_path": "str (local .hdf5 file)", "robot_embodiment": "str"},
        example_response={"upload_id": "upl_abc123", "episodes_received": 50, "status": "queued"},
    ),
    APIEndpoint(
        name="fine_tune",
        method="POST",
        path="/v1/finetune",
        description="Launch a fine-tuning job using uploaded demonstrations.",
        params={
            "upload_id": "str",
            "base_model": "str (default gr00t-n1.6)",
            "steps": "int (default 2000)",
            "learning_rate": "float (default 1e-4)",
        },
        example_response={"job_id": "job_xyz789", "status": "running", "estimated_minutes": 35},
    ),
    APIEndpoint(
        name="list_checkpoints",
        method="GET",
        path="/v1/checkpoints",
        description="List fine-tuned model checkpoints available for the partner.",
        params={"job_id": "str (optional filter)", "limit": "int (default 10)"},
        example_response={
            "checkpoints": [
                {"id": "ckpt_001", "job_id": "job_xyz789", "step": 2000, "mae": 0.013}
            ]
        },
    ),
    APIEndpoint(
        name="evaluate",
        method="POST",
        path="/v1/evaluate",
        description="Run a closed-loop simulation evaluation for a checkpoint.",
        params={
            "checkpoint_id": "str",
            "task_name": "str",
            "num_episodes": "int (default 20)",
        },
        example_response={"eval_id": "eval_456", "success_rate": 0.75, "mean_latency_ms": 231},
    ),
    APIEndpoint(
        name="dagger_start",
        method="POST",
        path="/v1/dagger/start",
        description="Start a DAgger (Dataset Aggregation) interactive training run.",
        params={
            "checkpoint_id": "str",
            "task_name": "str",
            "max_steps": "int (default 5000)",
            "intervention_threshold": "float (default 0.4)",
        },
        example_response={"dagger_id": "dag_111", "status": "running", "port": 8021},
    ),
    APIEndpoint(
        name="dagger_status",
        method="GET",
        path="/v1/dagger/{dagger_id}/status",
        description="Poll the status and metrics of an active DAgger run.",
        params={"dagger_id": "str (path param)"},
        example_response={
            "dagger_id": "dag_111",
            "step": 1200,
            "interventions": 34,
            "current_mae": 0.021,
            "status": "running",
        },
    ),
    APIEndpoint(
        name="deploy_checkpoint",
        method="POST",
        path="/v1/checkpoints/{checkpoint_id}/deploy",
        description="Deploy a checkpoint to the live inference service.",
        params={"checkpoint_id": "str (path param)", "replicas": "int (default 1)"},
        example_response={"deployment_id": "dep_222", "endpoint": "https://api.oci-robot.cloud/infer/dep_222", "status": "active"},
    ),
    APIEndpoint(
        name="inference",
        method="POST",
        path="/v1/infer",
        description="Run a single-step robot action inference from an observation.",
        params={
            "deployment_id": "str",
            "image_b64": "str (base64 RGB image)",
            "state_vector": "list[float] (joint positions)",
            "task_instruction": "str",
        },
        example_response={"action": [0.02, -0.01, 0.0, 0.0, 0.0, 0.0, 0.5], "latency_ms": 227},
    ),
    APIEndpoint(
        name="get_metrics",
        method="GET",
        path="/v1/metrics",
        description="Retrieve usage, cost, and performance metrics for the partner account.",
        params={"start_date": "str ISO-8601", "end_date": "str ISO-8601", "granularity": "str (hour|day|week)"},
        example_response={
            "inference_calls": 12400,
            "finetune_gpu_hours": 14.2,
            "cost_usd": 18.34,
            "avg_latency_ms": 229,
        },
    ),
    APIEndpoint(
        name="stream_telemetry",
        method="GET",
        path="/v1/telemetry/stream",
        description="Server-sent events stream of real-time robot telemetry during deployment.",
        params={"deployment_id": "str", "fields": "str comma-separated (joint_pos,ee_pose,gripper)"},
        example_response={"event": "telemetry", "data": {"joint_pos": [0.1, -0.2, 0.3], "gripper": 0.8}},
    ),
]

# Ordered endpoint names per tier
TIER_ENDPOINTS = {
    "pilot":      ["health", "list_tasks", "upload_demos", "fine_tune", "list_checkpoints", "evaluate"],
    "growth":     ["health", "list_tasks", "upload_demos", "fine_tune", "list_checkpoints",
                   "evaluate", "dagger_start", "dagger_status", "deploy_checkpoint"],
    "enterprise": [ep.name for ep in ENDPOINTS],  # all 12
}

ENDPOINT_MAP: Dict[str, APIEndpoint] = {ep.name: ep for ep in ENDPOINTS}


# ---------------------------------------------------------------------------
# SDK generator
# ---------------------------------------------------------------------------

def _method_snippet(ep: APIEndpoint, indent: str = "    ") -> str:
    """Return a single method string for the given endpoint."""
    method_name = ep.name
    is_path_param = "{" in ep.path

    # Build param signature
    sig_parts = ["self"]
    for pname, pdesc in ep.params.items():
        clean = pname.replace("{", "").replace("}", "")
        sig_parts.append(clean + "=None")
    sig = ", ".join(sig_parts)

    # Build docstring
    param_doc_lines = []
    for pname, pdesc in ep.params.items():
        clean = pname.replace("{", "").replace("}", "")
        param_doc_lines.append(f"{indent}    {clean}: {pdesc}")

    param_doc = "\n".join(param_doc_lines) if param_doc_lines else f"{indent}    (no parameters)"
    example_str = json.dumps(ep.example_response, indent=8)

    # Build URL
    url_line = f'url = self.base_url + "{ep.path}"'
    if is_path_param:
        # replace {param} with f-string substitution
        fpath = ep.path
        for pname in ep.params:
            if "{" in pname:
                clean = pname.replace("{", "").replace("}", "")
                fpath = fpath.replace(pname, "{" + clean + "}")
        url_line = f'url = self.base_url + f"{fpath}"'

    # Build request call
    if ep.method == "GET":
        # collect non-path params for query string
        query_params = [p for p in ep.params if "{" not in p]
        if query_params:
            params_dict = "{" + ", ".join(f'"{p}": {p}' for p in query_params) + "}"
            req_line = f"resp = requests.get(url, headers=self._headers(), params={{{', '.join(repr(p) + ': ' + p for p in query_params)}}})"
        else:
            req_line = "resp = requests.get(url, headers=self._headers())"
    else:
        body_params = [p for p in ep.params if "{" not in p]
        if body_params:
            body_dict = "{" + ", ".join(f'"{p}": {p}' for p in body_params) + "}"
            req_line = f"resp = requests.post(url, headers=self._headers(), json={body_dict})"
        else:
            req_line = "resp = requests.post(url, headers=self._headers())"

    lines = [
        f"{indent}def {method_name}({sig}):",
        f'{indent}    """',
        f"{indent}    {ep.description}",
        f"",
        f"{indent}    Parameters:",
        param_doc,
        f"",
        f"{indent}    Example response:",
        f"{indent}    {example_str.strip()}",
        f'{indent}    """',
        f"{indent}    {url_line}",
        f"{indent}    {req_line}",
        f"{indent}    resp.raise_for_status()",
        f"{indent}    return resp.json()",
        "",
    ]
    return "\n".join(lines)


def generate_python_sdk(partner: PartnerConfig) -> str:
    """Return a complete standalone Python SDK string for the given partner."""
    enabled = set(partner.enabled_endpoints)
    methods_code = "\n".join(
        _method_snippet(ENDPOINT_MAP[name])
        for name in TIER_ENDPOINTS[partner.tier]
        if name in enabled and name in ENDPOINT_MAP
    )

    sdk = textwrap.dedent(f'''\
        #!/usr/bin/env python3
        """
        OCI Robot Cloud Python SDK — generated for {partner.partner_name}
        Tier: {partner.tier}
        Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

        Usage:
            from robot_cloud_client import RobotCloudClient
            client = RobotCloudClient(api_key="{partner.api_key}", base_url="{partner.base_url}")
            print(client.health())
        """

        import requests
        from typing import Any, Dict, List, Optional


        class RobotCloudClient:
            """Python client for the OCI Robot Cloud API ({partner.tier} tier)."""

            def __init__(self, api_key: str, base_url: str = "{partner.base_url}"):
                """
                Initialize the client.

                Args:
                    api_key: Your {partner.partner_name} API key.
                    base_url: API base URL (default: {partner.base_url}).
                """
                self.api_key = api_key
                self.base_url = base_url.rstrip("/")

            def _headers(self) -> Dict[str, str]:
                return {{
                    "Authorization": f"Bearer {{self.api_key}}",
                    "Content-Type": "application/json",
                    "X-Partner": "{partner.partner_name}",
                }}

        {methods_code}
        ''')
    # Re-indent methods section
    return sdk


# ---------------------------------------------------------------------------
# HTML quickstart generator
# ---------------------------------------------------------------------------

def _curl_example(ep: APIEndpoint, partner: PartnerConfig) -> str:
    """Return a formatted curl one-liner for the endpoint."""
    url = f"{partner.base_url}{ep.path}"
    if "{" in url:
        url = url.replace("{dagger_id}", "dag_111").replace("{checkpoint_id}", "ckpt_001")

    auth = f'-H "Authorization: Bearer {partner.api_key}"'
    if ep.method == "GET":
        return f"curl -X GET {url} {auth}"
    else:
        # Use first two params as sample body
        sample = {k.replace("{", "").replace("}", ""): f"<{k}>" for k in list(ep.params.keys())[:2]}
        body = json.dumps(sample)
        return f'curl -X POST {url} {auth} -H "Content-Type: application/json" -d \'{body}\''


def generate_quickstart_html(partner: PartnerConfig, sdk_code: str) -> str:
    """Return a dark-themed HTML quickstart page for the given partner."""
    enabled_eps = [
        ENDPOINT_MAP[name]
        for name in TIER_ENDPOINTS[partner.tier]
        if name in partner.enabled_endpoints and name in ENDPOINT_MAP
    ]

    # Endpoint reference table rows
    table_rows = "\n".join(
        f"""        <tr>
          <td><code>{ep.name}</code></td>
          <td><span class="badge badge-{ep.method.lower()}">{ep.method}</span></td>
          <td><code>{ep.path}</code></td>
          <td>{ep.description}</td>
        </tr>"""
        for ep in enabled_eps
    )

    # curl examples
    curl_blocks = "\n".join(
        f"""      <div class="curl-block">
        <div class="curl-title">{ep.name}</div>
        <pre class="code-block">{_curl_example(ep, partner)}</pre>
      </div>"""
        for ep in enabled_eps
    )

    # Escape SDK code for HTML
    sdk_escaped = sdk_code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud SDK — {partner.partner_name}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #1e293b;
      color: #e2e8f0;
      line-height: 1.6;
    }}
    a {{ color: #60a5fa; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Layout */
    header {{
      background: #0f172a;
      border-bottom: 3px solid #C74634;
      padding: 1.5rem 2rem;
      display: flex;
      align-items: center;
      gap: 1.5rem;
    }}
    .oracle-logo {{
      font-size: 1.4rem;
      font-weight: 700;
      color: #C74634;
      letter-spacing: -0.5px;
    }}
    header h1 {{
      font-size: 1.25rem;
      font-weight: 600;
      color: #f1f5f9;
    }}
    .tier-badge {{
      margin-left: auto;
      background: #C74634;
      color: #fff;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      padding: 0.2rem 0.7rem;
      border-radius: 999px;
      letter-spacing: 0.05em;
    }}

    main {{ max-width: 1100px; margin: 0 auto; padding: 2.5rem 2rem; }}

    h2 {{
      color: #C74634;
      font-size: 1.2rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin: 2.5rem 0 1rem;
      padding-bottom: 0.4rem;
      border-bottom: 1px solid #334155;
    }}
    h3 {{ color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; margin-bottom: 0.5rem; }}

    /* Code blocks — Monokai-style */
    .code-block {{
      background: #272822;
      color: #f8f8f2;
      font-family: "JetBrains Mono", "Fira Code", "Courier New", monospace;
      font-size: 0.78rem;
      line-height: 1.7;
      padding: 1.25rem 1.5rem;
      border-radius: 8px;
      overflow-x: auto;
      border-left: 3px solid #C74634;
      white-space: pre;
    }}

    /* Endpoint table */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      margin-top: 0.5rem;
    }}
    th {{
      background: #0f172a;
      color: #94a3b8;
      text-transform: uppercase;
      font-size: 0.72rem;
      letter-spacing: 0.06em;
      padding: 0.6rem 1rem;
      text-align: left;
      border-bottom: 2px solid #334155;
    }}
    td {{
      padding: 0.65rem 1rem;
      border-bottom: 1px solid #1e3a5f22;
      vertical-align: top;
    }}
    tr:hover td {{ background: #1e3a5f33; }}
    code {{
      background: #0f172a;
      color: #67e8f9;
      padding: 0.1em 0.35em;
      border-radius: 4px;
      font-size: 0.82em;
    }}

    /* Method badges */
    .badge {{
      display: inline-block;
      padding: 0.15em 0.5em;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .badge-get  {{ background: #134e4a; color: #34d399; }}
    .badge-post {{ background: #1e3a5f; color: #60a5fa; }}

    /* curl blocks */
    .curl-block {{ margin-bottom: 1.25rem; }}
    .curl-title {{
      font-size: 0.8rem;
      color: #94a3b8;
      margin-bottom: 0.35rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    /* Info card */
    .info-card {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }}
    .info-card .label {{ color: #64748b; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .info-card .value {{ color: #e2e8f0; font-weight: 600; margin-top: 0.2rem; }}
    .info-card .value code {{ background: transparent; color: #67e8f9; }}

    footer {{
      text-align: center;
      padding: 2rem;
      color: #475569;
      font-size: 0.8rem;
      border-top: 1px solid #334155;
      margin-top: 3rem;
    }}
  </style>
</head>
<body>
<header>
  <div class="oracle-logo">ORACLE</div>
  <h1>OCI Robot Cloud API &mdash; {partner.partner_name} Quickstart</h1>
  <span class="tier-badge">{partner.tier}</span>
</header>

<main>

  <h2>Partner Details</h2>
  <div class="info-card">
    <div>
      <div class="label">Partner</div>
      <div class="value">{partner.partner_name}</div>
    </div>
    <div>
      <div class="label">Tier</div>
      <div class="value">{partner.tier.capitalize()}</div>
    </div>
    <div>
      <div class="label">Base URL</div>
      <div class="value"><code>{partner.base_url}</code></div>
    </div>
    <div>
      <div class="label">Assigned Ports</div>
      <div class="value">{", ".join(str(p) for p in partner.assigned_ports)}</div>
    </div>
    <div>
      <div class="label">Endpoints Enabled</div>
      <div class="value">{len(enabled_eps)} of {len(ENDPOINTS)}</div>
    </div>
  </div>

  <h2>Python SDK</h2>
  <pre class="code-block">{sdk_escaped}</pre>

  <h2>Endpoint Reference</h2>
  <table>
    <thead>
      <tr><th>Name</th><th>Method</th><th>Path</th><th>Description</th></tr>
    </thead>
    <tbody>
{table_rows}
    </tbody>
  </table>

  <h2>curl Examples</h2>
{curl_blocks}

</main>

<footer>
  &copy; {datetime.utcnow().year} Oracle Corporation &mdash; OCI Robot Cloud &mdash;
  Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Mock partner catalog
# ---------------------------------------------------------------------------

def generate_all_partners() -> List[PartnerConfig]:
    """Return 3 mock design partners across tiers."""
    return [
        PartnerConfig(
            partner_name="Agility Robotics",
            tier="enterprise",
            api_key="agility-oci-key-e3f9a1b2c4d5",
            base_url="https://agility.api.oci-robot.cloud",
            assigned_ports=[8001, 8003, 8021, 8022, 8023, 8024],
            enabled_endpoints=TIER_ENDPOINTS["enterprise"],
        ),
        PartnerConfig(
            partner_name="Figure AI",
            tier="growth",
            api_key="figure-oci-key-7a8b2c3d4e5f",
            base_url="https://figure.api.oci-robot.cloud",
            assigned_ports=[8001, 8003, 8021, 8022],
            enabled_endpoints=TIER_ENDPOINTS["growth"],
        ),
        PartnerConfig(
            partner_name="Boston Dynamics",
            tier="pilot",
            api_key="bd-oci-key-1c2d3e4f5a6b",
            base_url="https://bostondynamics.api.oci-robot.cloud",
            assigned_ports=[8001, 8003],
            enabled_endpoints=TIER_ENDPOINTS["pilot"],
        ),
    ]


# ---------------------------------------------------------------------------
# Index HTML
# ---------------------------------------------------------------------------

def generate_index_html(partners: List[PartnerConfig]) -> str:
    """Return a combined index.html linking to all partner pages."""
    rows = "\n".join(
        f"""    <tr>
      <td>{p.partner_name}</td>
      <td><span class="badge badge-{p.tier}">{p.tier.capitalize()}</span></td>
      <td>{len(p.enabled_endpoints)}</td>
      <td><a href="{p.partner_name.replace(' ', '_').lower()}_quickstart.html">View Docs</a></td>
    </tr>"""
        for p in partners
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Robot Cloud — Partner SDK Index</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #1e293b; color: #e2e8f0;
           max-width: 800px; margin: 3rem auto; padding: 0 1.5rem; }}
    h1 {{ color: #C74634; margin-bottom: 0.25rem; }}
    p  {{ color: #94a3b8; margin-bottom: 2rem; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background: #0f172a; color: #94a3b8; text-transform: uppercase;
          font-size: 0.72rem; letter-spacing: 0.06em; padding: 0.6rem 1rem;
          text-align: left; border-bottom: 2px solid #334155; }}
    td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #334155; }}
    a  {{ color: #60a5fa; }}
    .badge {{ display:inline-block; padding:0.15em 0.5em; border-radius:4px;
              font-size:0.72rem; font-weight:700; text-transform:uppercase; }}
    .badge-pilot      {{ background:#1c1c00; color:#facc15; }}
    .badge-growth     {{ background:#134e4a; color:#34d399; }}
    .badge-enterprise {{ background:#3b0764; color:#c084fc; }}
    footer {{ margin-top:3rem; text-align:center; color:#475569; font-size:0.8rem; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Partner SDK Index</h1>
  <p>Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</p>
  <table>
    <thead><tr><th>Partner</th><th>Tier</th><th>Endpoints</th><th>Docs</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
  <footer>&copy; {datetime.utcnow().year} Oracle Corporation</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate OCI Robot Cloud partner SDK docs.",
    )
    parser.add_argument("--partner", metavar="NAME", default=None,
                        help="Generate docs only for this partner name (substring match).")
    parser.add_argument("--output-dir", metavar="DIR", default="/tmp/sdk_docs/",
                        help="Directory to write HTML files into (default: /tmp/sdk_docs/).")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    all_partners = generate_all_partners()

    if args.partner:
        partners = [p for p in all_partners if args.partner.lower() in p.partner_name.lower()]
        if not partners:
            print(f"No partner matching '{args.partner}' found.")
            print("Available:", ", ".join(p.partner_name for p in all_partners))
            return
    else:
        partners = all_partners

    for partner in partners:
        sdk_code = generate_python_sdk(partner)
        html = generate_quickstart_html(partner, sdk_code)
        filename = partner.partner_name.replace(" ", "_").lower() + "_quickstart.html"
        out_path = os.path.join(args.output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"[{partner.tier:10s}] {partner.partner_name:20s} -> {out_path}")

    # Always write index when generating all partners
    if not args.partner:
        index_path = os.path.join(args.output_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(generate_index_html(all_partners))
        print(f"{'':33}index -> {index_path}")


if __name__ == "__main__":
    main()
