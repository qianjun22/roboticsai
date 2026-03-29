#!/usr/bin/env python3
"""
model_registry.py — Lightweight model registry for GR00T fine-tuned checkpoints.

Tracks checkpoint metadata, eval results, training configs, and deployment history.
Exposes a REST API and CLI for checkpoint management.

Usage:
    # FastAPI service (port 8009)
    python src/api/model_registry.py --serve --port 8009

    # CLI usage
    python src/api/model_registry.py register \
        --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 \
        --tag "1000-demo-bc" \
        --notes "1000 demos, 5k steps, loss 0.099"

    python src/api/model_registry.py list
    python src/api/model_registry.py promote --tag "1000-demo-bc" --env production

    # Initialize with mock data
    python src/api/model_registry.py --mock
"""

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class TrainingConfig:
    n_demos: int = 0
    train_steps: int = 0
    final_loss: float = 0.0
    training_time_min: float = 0.0
    robot_type: str = "franka"
    base_model: str = "nvidia/GR00T-N1.5-3B"

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EvalResults:
    success_rate: float = 0.0
    n_episodes: int = 0
    avg_latency_ms: float = 0.0
    eval_date: str = ""
    checkpoint_id: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "EvalResults":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CheckpointRecord:
    id: str
    tag: str
    checkpoint_path: str
    created_at: str
    training_config: TrainingConfig
    eval_results: Optional[EvalResults]
    notes: str
    env: str          # "draft" | "staging" | "production"
    promoted_at: Optional[str]
    parent_id: Optional[str]

    @classmethod
    def from_dict(cls, d: dict) -> "CheckpointRecord":
        tc = TrainingConfig.from_dict(d.get("training_config", {}))
        er_raw = d.get("eval_results")
        er = EvalResults.from_dict(er_raw) if er_raw else None
        return cls(
            id=d["id"],
            tag=d["tag"],
            checkpoint_path=d["checkpoint_path"],
            created_at=d["created_at"],
            training_config=tc,
            eval_results=er,
            notes=d.get("notes", ""),
            env=d.get("env", "draft"),
            promoted_at=d.get("promoted_at"),
            parent_id=d.get("parent_id"),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        # Flatten nested dataclasses back to plain dicts (asdict already does this)
        return d


# ── Registry ──────────────────────────────────────────────────────────────────

DEFAULT_REGISTRY_PATH = Path.home() / ".oci_robot_registry.json"


class ModelRegistry:
    """Lightweight file-backed registry for GR00T fine-tuned checkpoints."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
        self._records: Dict[str, CheckpointRecord] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                self._records = {
                    tag: CheckpointRecord.from_dict(rec)
                    for tag, rec in raw.items()
                }
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"[Registry] Warning: could not load {self.path}: {exc}")
                self._records = {}

    def _save(self):
        self.path.write_text(
            json.dumps(
                {tag: rec.to_dict() for tag, rec in self._records.items()},
                indent=2,
                default=str,
            )
        )

    # ── Core operations ───────────────────────────────────────────────────────

    def register(
        self,
        checkpoint_path: str,
        tag: str,
        training_config: Optional[dict] = None,
        notes: str = "",
        parent_tag: Optional[str] = None,
    ) -> CheckpointRecord:
        """Register a new checkpoint. Raises ValueError if tag already exists."""
        if tag in self._records:
            raise ValueError(f"Tag '{tag}' already registered. Use a unique tag.")

        parent_id = self._records[parent_tag].id if parent_tag and parent_tag in self._records else None

        rec = CheckpointRecord(
            id=str(uuid.uuid4())[:8],
            tag=tag,
            checkpoint_path=str(checkpoint_path),
            created_at=_now(),
            training_config=TrainingConfig.from_dict(training_config or {}),
            eval_results=None,
            notes=notes,
            env="draft",
            promoted_at=None,
            parent_id=parent_id,
        )
        self._records[tag] = rec
        self._save()
        return rec

    def add_eval_result(self, tag: str, eval_results: dict) -> CheckpointRecord:
        """Attach eval results to an existing checkpoint."""
        rec = self._get_or_raise(tag)
        er = EvalResults.from_dict(eval_results)
        er.checkpoint_id = rec.id
        if not er.eval_date:
            er.eval_date = _now()
        rec.eval_results = er
        self._save()
        return rec

    def promote(self, tag: str, env: str) -> CheckpointRecord:
        """Promote a checkpoint to staging or production."""
        if env not in ("staging", "production"):
            raise ValueError(f"env must be 'staging' or 'production', got '{env}'")
        rec = self._get_or_raise(tag)
        rec.env = env
        rec.promoted_at = _now()
        self._save()
        return rec

    def list_checkpoints(self, env: Optional[str] = None) -> List[CheckpointRecord]:
        """Return all checkpoints, optionally filtered by env."""
        recs = list(self._records.values())
        if env:
            recs = [r for r in recs if r.env == env]
        recs.sort(key=lambda r: r.created_at, reverse=True)
        return recs

    def get_checkpoint(self, tag: str) -> CheckpointRecord:
        return self._get_or_raise(tag)

    def get_best(self, metric: str = "success_rate") -> Optional[CheckpointRecord]:
        """Return the checkpoint with the highest value for the given metric."""
        candidates = [r for r in self._records.values() if r.eval_results is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda r: getattr(r.eval_results, metric, 0.0))

    def get_lineage(self, tag: str) -> List[CheckpointRecord]:
        """Walk parent chain back to the root; returns list from root → tag."""
        rec = self._get_or_raise(tag)
        chain = [rec]
        visited = {rec.id}
        # Build id → record map for parent lookup
        by_id = {r.id: r for r in self._records.values()}
        while chain[-1].parent_id and chain[-1].parent_id not in visited:
            parent = by_id.get(chain[-1].parent_id)
            if parent is None:
                break
            visited.add(parent.id)
            chain.append(parent)
        chain.reverse()
        return chain

    def export_table(self) -> str:
        """Render a Markdown table of all checkpoints."""
        recs = self.list_checkpoints()
        lines = [
            "| Tag | Env | Demos | Steps | Loss | Success Rate | Notes |",
            "|-----|-----|-------|-------|------|--------------|-------|",
        ]
        for r in recs:
            sr = f"{r.eval_results.success_rate:.0%}" if r.eval_results else "—"
            lines.append(
                f"| {r.tag} | {r.env} | {r.training_config.n_demos} "
                f"| {r.training_config.train_steps} "
                f"| {r.training_config.final_loss:.3f} "
                f"| {sr} | {r.notes} |"
            )
        return "\n".join(lines)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_or_raise(self, tag: str) -> CheckpointRecord:
        if tag not in self._records:
            raise KeyError(f"Tag '{tag}' not found in registry.")
        return self._records[tag]


# ── Mock data ─────────────────────────────────────────────────────────────────

def populate_mock_data(registry: ModelRegistry):
    """Pre-populate the registry with representative training history."""

    # 1. baseline-bc-500
    if "baseline-bc-500" not in registry._records:
        registry.register(
            checkpoint_path="/tmp/finetune_500_5k/checkpoint-5000",
            tag="baseline-bc-500",
            training_config={
                "n_demos": 500,
                "train_steps": 5000,
                "final_loss": 0.164,
                "training_time_min": 21.2,
                "robot_type": "franka",
                "base_model": "nvidia/GR00T-N1.5-3B",
            },
            notes="500 demos, 5k steps BC baseline",
        )
        registry.add_eval_result(
            "baseline-bc-500",
            {
                "success_rate": 0.03,
                "n_episodes": 100,
                "avg_latency_ms": 231.0,
                "eval_date": "2026-02-10T08:00:00Z",
            },
        )

    # 2. bc-1000  (child of baseline-bc-500)
    if "bc-1000" not in registry._records:
        registry.register(
            checkpoint_path="/tmp/finetune_1000_5k/checkpoint-5000",
            tag="bc-1000",
            training_config={
                "n_demos": 1000,
                "train_steps": 5000,
                "final_loss": 0.099,
                "training_time_min": 35.4,
                "robot_type": "franka",
                "base_model": "nvidia/GR00T-N1.5-3B",
            },
            notes="1000 demos, 5k steps, loss 0.099",
            parent_tag="baseline-bc-500",
        )
        registry.add_eval_result(
            "bc-1000",
            {
                "success_rate": 0.05,
                "n_episodes": 100,
                "avg_latency_ms": 229.0,
                "eval_date": "2026-02-20T09:00:00Z",
            },
        )
        registry.promote("bc-1000", "staging")

    # 3. dagger-run4-iter3  (child of bc-1000)
    if "dagger-run4-iter3" not in registry._records:
        registry.register(
            checkpoint_path="/tmp/dagger_run4_iter3/checkpoint-6000",
            tag="dagger-run4-iter3",
            training_config={
                "n_demos": 120,
                "train_steps": 6000,
                "final_loss": 0.041,
                "training_time_min": 18.7,
                "robot_type": "franka",
                "base_model": "nvidia/GR00T-N1.5-3B",
            },
            notes="120 DAgger episodes, 3 iterations, closed-loop",
            parent_tag="bc-1000",
        )
        registry.add_eval_result(
            "dagger-run4-iter3",
            {
                "success_rate": 0.65,
                "n_episodes": 100,
                "avg_latency_ms": 227.0,
                "eval_date": "2026-03-15T10:00:00Z",
            },
        )
        registry.promote("dagger-run4-iter3", "production")

    print("[Registry] Mock data populated.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env_badge(env: str) -> str:
    colors = {"production": "#22c55e", "staging": "#f59e0b", "draft": "#6b7280"}
    return (
        f'<span style="background:{colors.get(env,"#6b7280")};color:#fff;'
        f'padding:2px 8px;border-radius:9999px;font-size:0.75rem">{env}</span>'
    )


# ── FastAPI app ───────────────────────────────────────────────────────────────

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="OCI Robot Cloud Model Registry", version="1.0.0")
    _registry: Optional[ModelRegistry] = None

    def _get_registry() -> ModelRegistry:
        global _registry
        if _registry is None:
            _registry = ModelRegistry()
        return _registry

    # ── Endpoints ─────────────────────────────────────────────────────────────

    @app.get("/checkpoints")
    def list_checkpoints_api(env: Optional[str] = None):
        recs = _get_registry().list_checkpoints(env=env)
        return [r.to_dict() for r in recs]

    @app.get("/checkpoints/best")
    def get_best_api(metric: str = "success_rate"):
        rec = _get_registry().get_best(metric=metric)
        if rec is None:
            raise HTTPException(status_code=404, detail="No checkpoints with eval results.")
        return rec.to_dict()

    @app.get("/checkpoints/{tag}")
    def get_checkpoint_api(tag: str):
        try:
            return _get_registry().get_checkpoint(tag).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/checkpoints")
    def register_checkpoint_api(body: dict):
        """
        Body: {checkpoint_path, tag, training_config?, notes?, parent_tag?}
        """
        required = ("checkpoint_path", "tag")
        for key in required:
            if key not in body:
                raise HTTPException(status_code=422, detail=f"Missing field: {key}")
        try:
            rec = _get_registry().register(
                checkpoint_path=body["checkpoint_path"],
                tag=body["tag"],
                training_config=body.get("training_config"),
                notes=body.get("notes", ""),
                parent_tag=body.get("parent_tag"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return rec.to_dict()

    @app.post("/checkpoints/{tag}/eval")
    def add_eval_api(tag: str, body: dict):
        """Body: {success_rate, n_episodes, avg_latency_ms, eval_date?}"""
        try:
            rec = _get_registry().add_eval_result(tag, body)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return rec.to_dict()

    @app.post("/checkpoints/{tag}/promote")
    def promote_api(tag: str, body: dict):
        """Body: {env: "staging"|"production"}"""
        env = body.get("env", "staging")
        try:
            rec = _get_registry().promote(tag, env)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return rec.to_dict()

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        reg = _get_registry()
        recs = reg.list_checkpoints()
        rows = ""
        for r in recs:
            sr = f"{r.eval_results.success_rate:.0%}" if r.eval_results else "—"
            lat = f"{r.eval_results.avg_latency_ms:.0f} ms" if r.eval_results else "—"
            lineage = reg.get_lineage(r.tag)
            lineage_str = " → ".join(x.tag for x in lineage) if len(lineage) > 1 else "—"
            promote_btn = ""
            if r.env == "draft":
                promote_btn = (
                    f'<button onclick="promote(\'{r.tag}\',\'staging\')" '
                    f'style="background:#f59e0b;color:#fff;border:none;'
                    f'padding:3px 10px;border-radius:6px;cursor:pointer">→ Staging</button>'
                )
            elif r.env == "staging":
                promote_btn = (
                    f'<button onclick="promote(\'{r.tag}\',\'production\')" '
                    f'style="background:#22c55e;color:#fff;border:none;'
                    f'padding:3px 10px;border-radius:6px;cursor:pointer">→ Production</button>'
                )
            rows += f"""
            <tr>
              <td style="font-family:monospace;color:#a5f3fc">{r.tag}</td>
              <td>{_env_badge(r.env)}</td>
              <td>{r.training_config.n_demos}</td>
              <td>{r.training_config.train_steps:,}</td>
              <td>{r.training_config.final_loss:.3f}</td>
              <td style="color:#4ade80;font-weight:bold">{sr}</td>
              <td>{lat}</td>
              <td style="color:#94a3b8;font-size:0.8rem">{lineage_str}</td>
              <td>{r.notes}</td>
              <td>{promote_btn}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>OCI Robot Cloud — Model Registry</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, sans-serif; padding: 2rem; }}
    h1 {{ font-size: 1.6rem; color: #7dd3fc; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }}
    th {{ background: #0f172a; color: #94a3b8; text-align: left; padding: 10px 14px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    td {{ padding: 10px 14px; border-top: 1px solid #1e293b; font-size: 0.875rem; vertical-align: middle; }}
    tr:nth-child(even) td {{ background: #172033; }}
    tr:hover td {{ background: #1a2744; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
    .footer {{ margin-top: 1.5rem; color: #475569; font-size: 0.8rem; }}
    .refresh-btn {{ float: right; background: #1d4ed8; color: #fff; border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Model Registry</h1>
  <p class="subtitle">{len(recs)} checkpoint(s) tracked &nbsp;|&nbsp; Registry: {reg.path}</p>
  <button class="refresh-btn" onclick="location.reload()">Refresh</button>
  <table>
    <thead>
      <tr>
        <th>Tag</th><th>Env</th><th>Demos</th><th>Steps</th>
        <th>Loss</th><th>Success Rate</th><th>Latency</th>
        <th>Lineage</th><th>Notes</th><th>Action</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="footer">Last rendered: {_now()} &nbsp;|&nbsp; OCI Robot Cloud v1.0</div>
  <script>
    async function promote(tag, env) {{
      if (!confirm('Promote ' + tag + ' to ' + env + '?')) return;
      const resp = await fetch('/checkpoints/' + tag + '/promote', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{env}})
      }});
      if (resp.ok) location.reload();
      else alert('Promote failed: ' + await resp.text());
    }}
  </script>
</body>
</html>"""
        return HTMLResponse(content=html)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli_register(args, registry: ModelRegistry):
    tc = {}
    if args.n_demos is not None:
        tc["n_demos"] = args.n_demos
    if args.train_steps is not None:
        tc["train_steps"] = args.train_steps
    if args.final_loss is not None:
        tc["final_loss"] = args.final_loss
    rec = registry.register(
        checkpoint_path=args.checkpoint,
        tag=args.tag,
        training_config=tc or None,
        notes=args.notes or "",
        parent_tag=args.parent_tag,
    )
    print(f"[Registry] Registered: {rec.tag} (id={rec.id})")


def _cli_list(args, registry: ModelRegistry):
    recs = registry.list_checkpoints(env=getattr(args, "env", None))
    if not recs:
        print("[Registry] No checkpoints found.")
        return
    fmt = "{:<28} {:<12} {:>6} {:>7} {:>6}  {:<12}  {}"
    print(fmt.format("TAG", "ENV", "DEMOS", "STEPS", "LOSS", "SUCCESS", "NOTES"))
    print("-" * 90)
    for r in recs:
        sr = f"{r.eval_results.success_rate:.0%}" if r.eval_results else "—"
        print(fmt.format(
            r.tag, r.env, r.training_config.n_demos,
            r.training_config.train_steps, f"{r.training_config.final_loss:.3f}",
            sr, r.notes[:40],
        ))


def _cli_promote(args, registry: ModelRegistry):
    rec = registry.promote(args.tag, args.env)
    print(f"[Registry] {rec.tag} promoted to {rec.env} at {rec.promoted_at}")


def _cli_eval(args, registry: ModelRegistry):
    er = {
        "success_rate": args.success_rate,
        "n_episodes": args.n_episodes,
        "avg_latency_ms": args.avg_latency_ms,
    }
    rec = registry.add_eval_result(args.tag, er)
    print(f"[Registry] Eval added to {rec.tag}: success_rate={rec.eval_results.success_rate:.0%}")


def _cli_export_table(args, registry: ModelRegistry):
    print(registry.export_table())


def main():
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud Model Registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server")
    parser.add_argument("--port", type=int, default=8009, help="Server port (default: 8009)")
    parser.add_argument("--registry", default=None, help="Path to registry JSON file")
    parser.add_argument("--mock", action="store_true", help="Populate mock data and exit")

    subparsers = parser.add_subparsers(dest="command")

    # register
    p_reg = subparsers.add_parser("register", help="Register a new checkpoint")
    p_reg.add_argument("--checkpoint", required=True, help="Path to checkpoint directory")
    p_reg.add_argument("--tag", required=True, help="Unique human-readable tag")
    p_reg.add_argument("--notes", default="", help="Free-text notes")
    p_reg.add_argument("--n-demos", type=int, dest="n_demos", default=None)
    p_reg.add_argument("--train-steps", type=int, dest="train_steps", default=None)
    p_reg.add_argument("--final-loss", type=float, dest="final_loss", default=None)
    p_reg.add_argument("--parent-tag", dest="parent_tag", default=None)

    # list
    p_list = subparsers.add_parser("list", help="List all checkpoints")
    p_list.add_argument("--env", default=None, help="Filter by env (draft/staging/production)")

    # promote
    p_prm = subparsers.add_parser("promote", help="Promote a checkpoint")
    p_prm.add_argument("--tag", required=True)
    p_prm.add_argument("--env", required=True, choices=["staging", "production"])

    # eval
    p_eval = subparsers.add_parser("eval", help="Add eval results to a checkpoint")
    p_eval.add_argument("--tag", required=True)
    p_eval.add_argument("--success-rate", type=float, dest="success_rate", required=True)
    p_eval.add_argument("--n-episodes", type=int, dest="n_episodes", default=100)
    p_eval.add_argument("--avg-latency-ms", type=float, dest="avg_latency_ms", default=0.0)

    # export-table
    subparsers.add_parser("export-table", help="Print Markdown table of all checkpoints")

    args = parser.parse_args()

    registry = ModelRegistry(registry_path=args.registry)

    if args.mock:
        populate_mock_data(registry)
        _cli_list(args, registry)
        return

    if args.command == "register":
        _cli_register(args, registry)
    elif args.command == "list":
        _cli_list(args, registry)
    elif args.command == "promote":
        _cli_promote(args, registry)
    elif args.command == "eval":
        _cli_eval(args, registry)
    elif args.command == "export-table":
        _cli_export_table(args, registry)
    elif args.serve:
        if not _FASTAPI_AVAILABLE:
            print("[Registry] FastAPI not installed. Run: pip install fastapi uvicorn")
            sys.exit(1)
        import importlib
        import src.api.model_registry as _self_mod  # noqa: F401
        global _registry
        _registry = registry
        print(f"[Registry] Starting on http://0.0.0.0:{args.port}")
        print(f"[Registry] Dashboard: http://localhost:{args.port}/dashboard")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        # Default: show help if no subcommand and not --serve/--mock
        if not args.serve:
            parser.print_help()


if __name__ == "__main__":
    main()
