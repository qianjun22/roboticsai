#!/usr/bin/env python3
"""
isaac_sim_config_validator.py

Validates Isaac Sim / Replicator scene configuration files before launching
expensive Synthetic Data Generation (SDG) runs.

Usage:
    python isaac_sim_config_validator.py [--config-dir PATH] [--output FILE]

    --config-dir  Directory containing *.json config files to validate.
                  If omitted, a set of mock configs is generated and validated.
    --output      Path for the HTML report (default: /tmp/isaac_sim_validator.html).

Exit code is 0 when all configs are valid, 1 when any have errors.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Core validation helpers
# ---------------------------------------------------------------------------

VALID_RESOLUTIONS = {(224, 224), (336, 336)}
FOV_MIN = 30.0
FOV_MAX = 120.0
REQUIRED_REPLICATOR_KEYS = {"scene_path", "num_frames", "randomization", "output_dir", "camera_configs"}
RANDOMIZATION_AXES = {"color", "size", "mass", "lighting", "distractor", "start_pos", "goal_pos"}
MIN_ENABLED_AXES = 2


def validate_camera_config(cam: dict) -> list[str]:
    """
    Validate a single camera configuration block.

    Checks:
    - ``resolution`` is present and equals 224x224 or 336x336.
    - ``fov`` is a number in the range [30, 120] degrees.
    - ``position`` is a list of exactly 3 finite floats.

    Returns a list of error strings (empty when the config is valid).
    """
    errors: list[str] = []

    # --- resolution ---
    res = cam.get("resolution")
    if res is None:
        errors.append("camera: missing 'resolution' field")
    elif not (isinstance(res, (list, tuple)) and len(res) == 2):
        errors.append(f"camera: 'resolution' must be a 2-element list, got {res!r}")
    else:
        w, h = res
        if (int(w), int(h)) not in VALID_RESOLUTIONS:
            errors.append(
                f"camera: resolution {w}x{h} is not supported; "
                f"allowed: {', '.join(f'{r[0]}x{r[1]}' for r in sorted(VALID_RESOLUTIONS))}"
            )

    # --- fov ---
    fov = cam.get("fov")
    if fov is None:
        errors.append("camera: missing 'fov' field")
    elif not isinstance(fov, (int, float)):
        errors.append(f"camera: 'fov' must be a number, got {type(fov).__name__}")
    else:
        if not (FOV_MIN <= float(fov) <= FOV_MAX):
            errors.append(
                f"camera: fov {fov} is out of range [{FOV_MIN}, {FOV_MAX}] degrees"
            )

    # --- position ---
    pos = cam.get("position")
    if pos is None:
        errors.append("camera: missing 'position' field")
    elif not isinstance(pos, (list, tuple)):
        errors.append(f"camera: 'position' must be a list, got {type(pos).__name__}")
    elif len(pos) != 3:
        errors.append(f"camera: 'position' must have exactly 3 elements, got {len(pos)}")
    else:
        for i, v in enumerate(pos):
            if not isinstance(v, (int, float)):
                errors.append(f"camera: 'position[{i}]' must be a float, got {type(v).__name__}")
            elif not math.isfinite(float(v)):
                errors.append(f"camera: 'position[{i}]' must be finite, got {v}")

    return errors


def validate_randomization_config(rand: dict) -> list[str]:
    """
    Validate the randomization sub-config.

    Rules:
    - At least ``MIN_ENABLED_AXES`` axes from ``RANDOMIZATION_AXES`` must be
      present and set to ``True``.
    - Each recognized axis value must be boolean.

    Returns a list of error strings (empty when valid).
    """
    errors: list[str] = []

    if not isinstance(rand, dict):
        return [f"randomization: expected a dict, got {type(rand).__name__}"]

    enabled: list[str] = []
    for axis in RANDOMIZATION_AXES:
        val = rand.get(axis)
        if val is None:
            continue  # optional — absence counts as disabled
        if not isinstance(val, bool):
            errors.append(
                f"randomization: axis '{axis}' must be a boolean, got {type(val).__name__}"
            )
        elif val:
            enabled.append(axis)

    if len(enabled) < MIN_ENABLED_AXES:
        errors.append(
            f"randomization: at least {MIN_ENABLED_AXES} axes must be enabled "
            f"(found {len(enabled)}: {enabled or 'none'}); "
            f"available axes: {sorted(RANDOMIZATION_AXES)}"
        )

    unknown = set(rand.keys()) - RANDOMIZATION_AXES
    if unknown:
        # Warn-level only; not appended as error here — caller may surface as warning.
        pass

    return errors


def validate_replicator_config(config: dict) -> list[str]:
    """
    Validate a top-level Replicator scene configuration dict.

    Checks:
    - All required keys are present.
    - ``scene_path`` is a non-empty string.
    - ``num_frames`` is a positive integer.
    - ``output_dir`` is a non-empty string.
    - ``camera_configs`` is a non-empty list; each element is validated via
      :func:`validate_camera_config`.
    - ``randomization`` is validated via :func:`validate_randomization_config`.

    Returns a list of error strings (empty when valid).
    """
    errors: list[str] = []

    if not isinstance(config, dict):
        return [f"config must be a JSON object, got {type(config).__name__}"]

    missing = REQUIRED_REPLICATOR_KEYS - set(config.keys())
    if missing:
        errors.append(f"missing required keys: {sorted(missing)}")

    # scene_path
    sp = config.get("scene_path")
    if sp is not None:
        if not isinstance(sp, str):
            errors.append(f"'scene_path' must be a string, got {type(sp).__name__}")
        elif not sp.strip():
            errors.append("'scene_path' must not be empty")

    # num_frames
    nf = config.get("num_frames")
    if nf is not None:
        if not isinstance(nf, int):
            errors.append(f"'num_frames' must be an integer, got {type(nf).__name__}")
        elif nf <= 0:
            errors.append(f"'num_frames' must be a positive integer, got {nf}")

    # output_dir
    od = config.get("output_dir")
    if od is not None:
        if not isinstance(od, str):
            errors.append(f"'output_dir' must be a string, got {type(od).__name__}")
        elif not od.strip():
            errors.append("'output_dir' must not be empty")

    # camera_configs
    cams = config.get("camera_configs")
    if cams is not None:
        if not isinstance(cams, list):
            errors.append(f"'camera_configs' must be a list, got {type(cams).__name__}")
        elif len(cams) == 0:
            errors.append("'camera_configs' must contain at least one camera")
        else:
            for idx, cam in enumerate(cams):
                if not isinstance(cam, dict):
                    errors.append(f"camera_configs[{idx}]: must be a dict")
                    continue
                for err in validate_camera_config(cam):
                    errors.append(f"camera_configs[{idx}]: {err}")

    # randomization
    rand = config.get("randomization")
    if rand is not None:
        for err in validate_randomization_config(rand):
            errors.append(err)

    return errors


def _collect_warnings(config: dict) -> list[str]:
    """Return advisory warnings for a config that may already be valid."""
    warnings: list[str] = []

    nf = config.get("num_frames")
    if isinstance(nf, int) and nf < 100:
        warnings.append(f"num_frames={nf} is very small; SDG runs typically need ≥100 frames")

    rand = config.get("randomization") or {}
    unknown = set(rand.keys()) - RANDOMIZATION_AXES
    if unknown:
        warnings.append(f"randomization: unrecognized axes will be ignored: {sorted(unknown)}")

    od = config.get("output_dir", "")
    if isinstance(od, str) and od and not os.path.isabs(od):
        warnings.append(f"output_dir '{od}' is a relative path; consider using an absolute path")

    return warnings


# ---------------------------------------------------------------------------
# Directory scanner
# ---------------------------------------------------------------------------

def scan_config_dir(path: str) -> list[dict]:
    """
    Recursively find all ``*.json`` files under *path*, parse each, run
    validation, and return a list of result dicts.

    Each result dict has the shape::

        {
            "file":     str,          # absolute path
            "valid":    bool,
            "errors":   list[str],
            "warnings": list[str],
        }
    """
    results: list[dict] = []
    config_dir = Path(path)
    json_files = sorted(config_dir.rglob("*.json"))

    if not json_files:
        print(f"[scan_config_dir] No *.json files found under '{path}'", file=sys.stderr)
        return results

    for fp in json_files:
        entry: dict[str, Any] = {
            "file": str(fp.resolve()),
            "valid": False,
            "errors": [],
            "warnings": [],
        }
        try:
            with fp.open("r", encoding="utf-8") as fh:
                config = json.load(fh)
        except json.JSONDecodeError as exc:
            entry["errors"].append(f"JSON parse error: {exc}")
            results.append(entry)
            continue
        except OSError as exc:
            entry["errors"].append(f"File read error: {exc}")
            results.append(entry)
            continue

        entry["errors"] = validate_replicator_config(config)
        entry["warnings"] = _collect_warnings(config)
        entry["valid"] = len(entry["errors"]) == 0
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Mock config generator
# ---------------------------------------------------------------------------

def generate_mock_configs(n: int = 5) -> list[dict]:
    """
    Generate *n* mock Replicator config dicts — a mix of valid and invalid
    entries useful for demonstrating the validator.

    Returns a list of raw config dicts (not result dicts).
    """
    rng = random.Random(42)

    def _good_cam() -> dict:
        res = rng.choice([[224, 224], [336, 336]])
        fov = round(rng.uniform(45.0, 90.0), 1)
        pos = [round(rng.uniform(-3.0, 3.0), 3) for _ in range(3)]
        return {"resolution": res, "fov": fov, "position": pos}

    configs: list[dict] = []

    for i in range(n):
        scenario = i % 5

        if scenario == 0:
            # Fully valid config
            configs.append({
                "scene_path": f"/isaac/scenes/table_top_{i}.usd",
                "num_frames": rng.randint(200, 2000),
                "output_dir": f"/tmp/sdg_output/run_{i:03d}",
                "camera_configs": [_good_cam(), _good_cam()],
                "randomization": {
                    "color": True,
                    "size": True,
                    "mass": False,
                    "lighting": True,
                    "distractor": True,
                    "start_pos": True,
                    "goal_pos": False,
                },
            })

        elif scenario == 1:
            # Bad resolution
            bad_cam = _good_cam()
            bad_cam["resolution"] = [128, 128]
            configs.append({
                "scene_path": f"/isaac/scenes/pick_place_{i}.usd",
                "num_frames": 500,
                "output_dir": f"/tmp/sdg_output/run_{i:03d}",
                "camera_configs": [bad_cam],
                "randomization": {"color": True, "lighting": True, "size": True},
            })

        elif scenario == 2:
            # Missing required keys
            configs.append({
                "scene_path": f"/isaac/scenes/peg_insert_{i}.usd",
                "num_frames": 800,
                # output_dir missing
                # camera_configs missing
                "randomization": {"color": True, "size": True, "mass": True},
            })

        elif scenario == 3:
            # Only 1 randomization axis enabled (below minimum)
            configs.append({
                "scene_path": f"/isaac/scenes/stack_{i}.usd",
                "num_frames": 400,
                "output_dir": f"/tmp/sdg_output/run_{i:03d}",
                "camera_configs": [_good_cam()],
                "randomization": {
                    "color": True,       # only 1 enabled
                    "size": False,
                    "lighting": False,
                },
            })

        else:
            # FOV out of range
            bad_cam = _good_cam()
            bad_cam["fov"] = 150.0
            configs.append({
                "scene_path": f"/isaac/scenes/door_open_{i}.usd",
                "num_frames": 1000,
                "output_dir": f"/tmp/sdg_output/run_{i:03d}",
                "camera_configs": [_good_cam(), bad_cam],
                "randomization": {
                    "color": True,
                    "size": True,
                    "mass": True,
                    "lighting": True,
                },
            })

    return configs


def _validate_mock_configs(n: int = 5) -> list[dict]:
    """Validate mock configs and return result dicts (no files on disk needed)."""
    results = []
    for idx, config in enumerate(generate_mock_configs(n)):
        errors = validate_replicator_config(config)
        warnings = _collect_warnings(config)
        results.append({
            "file": f"<mock config #{idx + 1}: {config.get('scene_path', 'unknown')}>",
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        })
    return results


# ---------------------------------------------------------------------------
# HTML report renderer
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Isaac Sim Config Validator Report</title>
<style>
  :root {{
    --bg:        #1e293b;
    --surface:   #273549;
    --border:    #374151;
    --text:      #e2e8f0;
    --muted:     #94a3b8;
    --oracle:    #C74634;
    --green:     #22c55e;
    --red:       #ef4444;
    --yellow:    #f59e0b;
    --card-bg:   #1e3a5f;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    padding: 2rem;
  }}
  h1 {{ color: var(--oracle); font-size: 1.6rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }}
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    text-align: center;
  }}
  .card .num {{ font-size: 2rem; font-weight: 700; }}
  .card .label {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card.valid   .num {{ color: var(--green); }}
  .card.invalid .num {{ color: var(--red); }}
  .card.warn    .num {{ color: var(--yellow); }}
  .card.total   .num {{ color: var(--text); }}
  h2 {{ color: var(--oracle); font-size: 1.1rem; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{
    background: var(--surface);
    color: var(--muted);
    text-align: left;
    padding: 0.65rem 0.8rem;
    border-bottom: 2px solid var(--border);
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  td {{
    padding: 0.65rem 0.8rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    font-size: 0.85rem;
  }}
  tr:hover td {{ background: rgba(255,255,255,0.03); }}
  .badge {{
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
  }}
  .badge.ok  {{ background: rgba(34,197,94,0.15);  color: var(--green); }}
  .badge.err {{ background: rgba(239,68,68,0.15);  color: var(--red);   }}
  .file-path {{ font-family: monospace; color: var(--muted); word-break: break-all; }}
  details {{ margin-top: 0.35rem; }}
  summary {{
    cursor: pointer;
    color: var(--muted);
    font-size: 0.78rem;
    user-select: none;
    list-style: none;
  }}
  summary::before {{ content: '▶ '; font-size: 0.65rem; }}
  details[open] summary::before {{ content: '▼ '; }}
  .err-list, .warn-list {{ margin-top: 0.4rem; padding-left: 1rem; }}
  .err-list li  {{ color: var(--red);    margin-bottom: 0.2rem; list-style: disc; }}
  .warn-list li {{ color: var(--yellow); margin-bottom: 0.2rem; list-style: disc; }}
  footer {{ color: var(--muted); font-size: 0.75rem; margin-top: 2.5rem; text-align: center; }}
</style>
</head>
<body>
<h1>Isaac Sim Config Validator</h1>
<p class="subtitle">OCI Robot Cloud — SDG pre-flight check &middot; {timestamp}</p>

<div class="summary-grid">
  <div class="card total">
    <div class="num">{total}</div>
    <div class="label">Total</div>
  </div>
  <div class="card valid">
    <div class="num">{valid_count}</div>
    <div class="label">Valid</div>
  </div>
  <div class="card invalid">
    <div class="num">{invalid_count}</div>
    <div class="label">Invalid</div>
  </div>
  <div class="card warn">
    <div class="num">{warn_count}</div>
    <div class="label">With Warnings</div>
  </div>
</div>

<h2>Per-File Results</h2>
<table>
  <thead>
    <tr>
      <th style="width:3rem">Status</th>
      <th>Config File</th>
      <th>Issues</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>

<footer>Generated by isaac_sim_config_validator.py &mdash; OCI Robot Cloud</footer>
</body>
</html>
"""


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(results: list[dict]) -> str:
    """
    Render a dark-theme HTML report from a list of validation result dicts.

    The report includes:
    - Summary cards (total / valid / invalid / with-warnings counts).
    - A per-file table with expandable error/warning details (CSS-only, no JS).

    Returns the HTML as a string.
    """
    import datetime

    total = len(results)
    valid_count = sum(1 for r in results if r["valid"])
    invalid_count = total - valid_count
    warn_count = sum(1 for r in results if r["warnings"])

    rows_html: list[str] = []
    for r in results:
        badge = '<span class="badge ok">&#10003; Valid</span>' if r["valid"] else '<span class="badge err">&#10007; Invalid</span>'
        fname = _escape(r["file"])

        issues_html = ""
        if r["errors"]:
            items = "\n".join(f"<li>{_escape(e)}</li>" for e in r["errors"])
            issues_html += (
                f'<details><summary>{len(r["errors"])} error(s)</summary>'
                f'<ul class="err-list">{items}</ul></details>'
            )
        if r["warnings"]:
            items = "\n".join(f"<li>{_escape(w)}</li>" for w in r["warnings"])
            issues_html += (
                f'<details><summary>{len(r["warnings"])} warning(s)</summary>'
                f'<ul class="warn-list">{items}</ul></details>'
            )
        if not r["errors"] and not r["warnings"]:
            issues_html = '<span style="color:var(--muted)">—</span>'

        rows_html.append(
            f"    <tr>\n"
            f"      <td>{badge}</td>\n"
            f"      <td><span class='file-path'>{fname}</span></td>\n"
            f"      <td>{issues_html}</td>\n"
            f"    </tr>"
        )

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return _HTML_TEMPLATE.format(
        timestamp=ts,
        total=total,
        valid_count=valid_count,
        invalid_count=invalid_count,
        warn_count=warn_count,
        rows="\n".join(rows_html),
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_summary(results: list[dict]) -> None:
    total = len(results)
    valid_count = sum(1 for r in results if r["valid"])
    print(f"\nIsaac Sim Config Validator — {total} config(s) checked")
    print(f"  Valid   : {valid_count}")
    print(f"  Invalid : {total - valid_count}")
    print(f"  Warnings: {sum(1 for r in results if r['warnings'])}")
    print()
    for r in results:
        status = "OK " if r["valid"] else "ERR"
        print(f"  [{status}] {r['file']}")
        for e in r["errors"]:
            print(f"         ERROR   {e}")
        for w in r["warnings"]:
            print(f"         WARNING {w}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Isaac Sim / Replicator scene config files before SDG runs."
    )
    parser.add_argument(
        "--config-dir",
        metavar="PATH",
        default=None,
        help="Directory containing *.json config files (default: use mock configs).",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        default="/tmp/isaac_sim_validator.html",
        help="Output path for the HTML report (default: /tmp/isaac_sim_validator.html).",
    )
    args = parser.parse_args(argv)

    if args.config_dir:
        if not os.path.isdir(args.config_dir):
            print(f"ERROR: --config-dir '{args.config_dir}' is not a directory.", file=sys.stderr)
            return 2
        results = scan_config_dir(args.config_dir)
        if not results:
            print("No *.json files found. Nothing to validate.")
            return 0
    else:
        print("No --config-dir specified; using generated mock configs.")
        results = _validate_mock_configs(n=5)

    _print_summary(results)

    html = render_html(results)
    output_path = args.output
    try:
        Path(output_path).write_text(html, encoding="utf-8")
        print(f"\nHTML report written to: {output_path}")
    except OSError as exc:
        print(f"WARNING: could not write HTML report: {exc}", file=sys.stderr)

    any_invalid = any(not r["valid"] for r in results)
    return 1 if any_invalid else 0


if __name__ == "__main__":
    sys.exit(main())
