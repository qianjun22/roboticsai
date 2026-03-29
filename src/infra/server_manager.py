#!/usr/bin/env python3
"""
server_manager.py — GR00T inference server lifecycle manager for OCI Robot Cloud.

Manages multiple GR00T server instances, each serving a different checkpoint.
Provides automatic health monitoring, restart on failure, and load-aware routing.

Features:
  - Start/stop individual server instances (each on a different GPU)
  - Health monitoring with automatic restart on failure
  - Round-robin or checkpoint-specific routing
  - Unified API proxy endpoint (port 8012) that routes to healthy servers
  - CLI for server management

Usage:
    # Start manager daemon (port 8012 proxy)
    python src/infra/server_manager.py --serve --port 8012

    # Register a checkpoint as a managed server
    python src/infra/server_manager.py register \\
        --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 \\
        --tag "1000-demo-bc" \\
        --gpu 4

    # Status of all managed servers
    python src/infra/server_manager.py status

    # Start all registered servers
    python src/infra/server_manager.py start-all

    # Mock mode (simulates 3 servers)
    python src/infra/server_manager.py --mock status
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("server-manager")

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_PORT = 8020
MAX_RESTARTS = 3
HEALTH_INTERVAL = 30          # seconds between monitor sweeps
STARTUP_TIMEOUT = 60          # seconds to wait for a server to become healthy
GROOT_SERVER_SCRIPT = str(
    Path(__file__).parent.parent / "inference" / "groot_franka_server.py"
)
DEFAULT_STATE_PATH = Path("/tmp/server_manager_state.json")
PROXY_PORT = 8012

# ── ServerInstance dataclass ──────────────────────────────────────────────────

@dataclass
class ServerInstance:
    tag: str
    checkpoint_path: str
    gpu_id: int
    port: int
    pid: Optional[int] = None
    status: str = "stopped"          # starting | healthy | unhealthy | stopped
    last_health_check: Optional[float] = None   # unix timestamp
    restart_count: int = 0
    requests_served: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ServerInstance":
        return cls(**d)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


# ── Mock data ─────────────────────────────────────────────────────────────────

def _build_mock_registry() -> Dict[str, ServerInstance]:
    mock = {
        "bc-500": ServerInstance(
            tag="bc-500",
            checkpoint_path="/tmp/finetune_500/checkpoint-5000",
            gpu_id=2,
            port=8020,
            pid=99001,
            status="healthy",
            last_health_check=time.time(),
            restart_count=0,
            requests_served=412,
        ),
        "bc-1000": ServerInstance(
            tag="bc-1000",
            checkpoint_path="/tmp/finetune_1000_5k/checkpoint-5000",
            gpu_id=4,
            port=8021,
            pid=99002,
            status="healthy",
            last_health_check=time.time(),
            restart_count=0,
            requests_served=837,
        ),
        "dagger-final": ServerInstance(
            tag="dagger-final",
            checkpoint_path="/tmp/dagger_final/checkpoint-10000",
            gpu_id=5,
            port=8022,
            pid=None,
            status="unhealthy",
            last_health_check=time.time() - 65,
            restart_count=2,
            requests_served=91,
        ),
    }
    return mock


# ── Mock health latencies ──────────────────────────────────────────────────────

_MOCK_LATENCY = {
    "bc-500": 180.0,
    "bc-1000": 245.0,
    "dagger-final": None,  # unhealthy — no response
}


# ── ServerManager ─────────────────────────────────────────────────────────────

class ServerManager:
    def __init__(self, mock: bool = False, state_path: Optional[Path] = None):
        self.mock = mock
        self.state_path = state_path or DEFAULT_STATE_PATH
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()

        if mock:
            self._registry: Dict[str, ServerInstance] = _build_mock_registry()
        else:
            self._registry: Dict[str, ServerInstance] = {}
            if self.state_path.exists():
                self.load_state(self.state_path)

    # ── Port allocation ────────────────────────────────────────────────────────

    def _next_port(self) -> int:
        used = {s.port for s in self._registry.values()}
        port = BASE_PORT
        while port in used:
            port += 1
        return port

    # ── Register ──────────────────────────────────────────────────────────────

    def register(
        self,
        checkpoint_path: str,
        tag: str,
        gpu_id: int,
        port: Optional[int] = None,
    ) -> ServerInstance:
        with self._lock:
            if tag in self._registry:
                raise ValueError(f"Tag '{tag}' already registered. Stop and deregister first.")
            assigned_port = port if port is not None else self._next_port()
            inst = ServerInstance(
                tag=tag,
                checkpoint_path=checkpoint_path,
                gpu_id=gpu_id,
                port=assigned_port,
            )
            self._registry[tag] = inst
            log.info("Registered server '%s' → GPU%d port %d checkpoint=%s",
                     tag, gpu_id, assigned_port, checkpoint_path)
            self.save_state(self.state_path)
            return inst

    # ── Start ─────────────────────────────────────────────────────────────────

    def start(self, tag: str) -> ServerInstance:
        with self._lock:
            inst = self._get_inst(tag)
            if inst.status in ("starting", "healthy"):
                log.info("Server '%s' already running (status=%s)", tag, inst.status)
                return inst
            inst.status = "starting"
            inst.pid = None

        if self.mock:
            # Simulate startup
            time.sleep(0.1)
            with self._lock:
                inst.status = "healthy"
                inst.last_health_check = time.time()
            log.info("[mock] Server '%s' started", tag)
            return inst

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(inst.gpu_id)

        cmd = [
            sys.executable,
            GROOT_SERVER_SCRIPT,
            "--checkpoint", inst.checkpoint_path,
            "--port", str(inst.port),
        ]
        log.info("Starting server '%s': %s", tag, " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with self._lock:
            inst.pid = proc.pid

        # Wait for the server to become healthy
        deadline = time.time() + STARTUP_TIMEOUT
        healthy = False
        while time.time() < deadline:
            time.sleep(2)
            result = self._do_health_check(inst)
            if result["status"] == "ok":
                healthy = True
                break

        with self._lock:
            if healthy:
                inst.status = "healthy"
                inst.last_health_check = time.time()
                log.info("Server '%s' is healthy on port %d", tag, inst.port)
            else:
                inst.status = "unhealthy"
                log.warning("Server '%s' failed to become healthy within %ds",
                            tag, STARTUP_TIMEOUT)
        self.save_state(self.state_path)
        return inst

    # ── Stop ──────────────────────────────────────────────────────────────────

    def stop(self, tag: str) -> ServerInstance:
        with self._lock:
            inst = self._get_inst(tag)
            pid = inst.pid
            inst.status = "stopped"
            inst.pid = None

        if self.mock:
            log.info("[mock] Server '%s' stopped", tag)
            self.save_state(self.state_path)
            return inst

        if pid is not None:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                log.info("Sent SIGTERM to process group of PID %d (server '%s')", pid, tag)
                # Give up to 10s for graceful shutdown
                for _ in range(10):
                    time.sleep(1)
                    try:
                        os.kill(pid, 0)   # probe — raises if gone
                    except ProcessLookupError:
                        break
                else:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                    log.warning("SIGKILL sent to '%s' (PID %d)", tag, pid)
            except (ProcessLookupError, PermissionError) as exc:
                log.warning("Could not signal PID %d for '%s': %s", pid, tag, exc)
        self.save_state(self.state_path)
        return inst

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self, tag: str) -> dict:
        with self._lock:
            inst = self._get_inst(tag)
        return self._do_health_check(inst)

    def _do_health_check(self, inst: ServerInstance) -> dict:
        if self.mock:
            latency = _MOCK_LATENCY.get(inst.tag)
            if latency is not None:
                return {"status": "ok", "latency_ms": latency}
            else:
                return {"status": "error", "latency_ms": None, "detail": "connection refused"}

        url = f"{inst.base_url}/health"
        t0 = time.perf_counter()
        try:
            resp = httpx.get(url, timeout=5.0)
            latency_ms = (time.perf_counter() - t0) * 1000
            if resp.status_code == 200:
                with self._lock:
                    inst.last_health_check = time.time()
                return {"status": "ok", "latency_ms": round(latency_ms, 1)}
            else:
                return {
                    "status": "error",
                    "latency_ms": round(latency_ms, 1),
                    "detail": f"HTTP {resp.status_code}",
                }
        except Exception as exc:
            return {"status": "error", "latency_ms": None, "detail": str(exc)}

    # ── Monitor loop ──────────────────────────────────────────────────────────

    def monitor_loop(self, interval: int = HEALTH_INTERVAL) -> None:
        """Background thread: checks all servers, restarts unhealthy ones."""
        log.info("Monitor loop started (interval=%ds)", interval)
        while not self._stop_monitor.wait(timeout=interval):
            with self._lock:
                tags = list(self._registry.keys())

            for tag in tags:
                with self._lock:
                    inst = self._registry.get(tag)
                    if inst is None or inst.status == "stopped":
                        continue

                result = self._do_health_check(inst)
                with self._lock:
                    inst = self._registry.get(tag)
                    if inst is None:
                        continue
                    if result["status"] == "ok":
                        if inst.status != "healthy":
                            log.info("Server '%s' recovered → healthy", tag)
                        inst.status = "healthy"
                        inst.last_health_check = time.time()
                    else:
                        log.warning("Server '%s' unhealthy: %s", tag, result.get("detail"))
                        inst.status = "unhealthy"
                        if inst.restart_count < MAX_RESTARTS:
                            inst.restart_count += 1
                            log.info("Restarting '%s' (attempt %d/%d)",
                                     tag, inst.restart_count, MAX_RESTARTS)
                            # Release lock before blocking start()
                            restart_tag = tag
                        else:
                            log.error(
                                "Server '%s' exceeded max restarts (%d). Leaving stopped.",
                                tag, MAX_RESTARTS,
                            )
                            inst.status = "stopped"
                            restart_tag = None

                if result["status"] != "ok" and restart_tag:
                    self.start(restart_tag)

            self.save_state(self.state_path)

    def start_monitor(self, interval: int = HEALTH_INTERVAL) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self.monitor_loop,
            args=(interval,),
            daemon=True,
            name="server-monitor",
        )
        self._monitor_thread.start()

    def stop_monitor(self) -> None:
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    # ── Routing ───────────────────────────────────────────────────────────────

    def get_healthy_server(self, tag: Optional[str] = None) -> Optional[ServerInstance]:
        with self._lock:
            if tag is not None:
                inst = self._registry.get(tag)
                if inst and inst.status == "healthy":
                    return inst
                return None
            # Return first healthy server (round-robin placeholder)
            for inst in self._registry.values():
                if inst.status == "healthy":
                    return inst
        return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_state(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = {tag: inst.to_dict() for tag, inst in self._registry.items()}
        try:
            path.write_text(json.dumps(data, indent=2))
        except OSError as exc:
            log.warning("Could not save state to %s: %s", path, exc)

    def load_state(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            with self._lock:
                for tag, d in data.items():
                    # On reload, mark previously running servers as unhealthy
                    # (they may have died while the manager was down)
                    if d.get("status") in ("healthy", "starting"):
                        d["status"] = "unhealthy"
                        d["pid"] = None
                    self._registry[tag] = ServerInstance.from_dict(d)
            log.info("Loaded %d server registrations from %s", len(data), path)
        except Exception as exc:
            log.warning("Could not load state from %s: %s", path, exc)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_inst(self, tag: str) -> ServerInstance:
        inst = self._registry.get(tag)
        if inst is None:
            raise KeyError(f"Unknown server tag: '{tag}'")
        return inst

    def list_servers(self) -> List[dict]:
        with self._lock:
            return [inst.to_dict() for inst in self._registry.values()]

    def start_all(self) -> None:
        with self._lock:
            tags = list(self._registry.keys())
        for tag in tags:
            self.start(tag)

    def stop_all(self) -> None:
        with self._lock:
            tags = list(self._registry.keys())
        for tag in tags:
            self.stop(tag)


# ── FastAPI proxy app ─────────────────────────────────────────────────────────

def build_app(manager: ServerManager) -> FastAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Server Manager",
        description="Lifecycle proxy for multiple GR00T inference server instances",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Proxy predict ─────────────────────────────────────────────────────────

    @app.post("/predict")
    async def proxy_predict(request: Request, tag: Optional[str] = None):
        inst = manager.get_healthy_server(tag)
        if inst is None:
            raise HTTPException(
                status_code=503,
                detail=f"No healthy server available{' for tag: ' + tag if tag else ''}",
            )
        target_url = f"{inst.base_url}/predict"
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(target_url, content=body, headers=headers)
            with manager._lock:
                inst.requests_served += 1
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
                headers={"X-Served-By": inst.tag},
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream error: {exc}")

    # ── Overall health ────────────────────────────────────────────────────────

    @app.get("/health")
    async def overall_health():
        servers = manager.list_servers()
        n_healthy = sum(1 for s in servers if s["status"] == "healthy")
        return {
            "status": "ok" if n_healthy > 0 else "degraded",
            "n_servers": len(servers),
            "n_healthy": n_healthy,
            "servers": [
                {
                    "tag": s["tag"],
                    "status": s["status"],
                    "port": s["port"],
                    "gpu_id": s["gpu_id"],
                    "restart_count": s["restart_count"],
                    "requests_served": s["requests_served"],
                }
                for s in servers
            ],
        }

    # ── List servers ──────────────────────────────────────────────────────────

    @app.get("/servers")
    async def list_servers():
        return manager.list_servers()

    # ── Start a server ────────────────────────────────────────────────────────

    @app.post("/servers/{tag}/start")
    async def start_server(tag: str):
        try:
            inst = manager.start(tag)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown tag: {tag}")
        return inst.to_dict()

    # ── Stop a server ─────────────────────────────────────────────────────────

    @app.post("/servers/{tag}/stop")
    async def stop_server(tag: str):
        try:
            inst = manager.stop(tag)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown tag: {tag}")
        return inst.to_dict()

    # ── Dashboard ─────────────────────────────────────────────────────────────

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        servers = manager.list_servers()

        def status_color(s: str) -> str:
            return {
                "healthy": "#22c55e",
                "unhealthy": "#ef4444",
                "starting": "#f59e0b",
                "stopped": "#6b7280",
            }.get(s, "#6b7280")

        def latency_badge(inst_dict: dict) -> str:
            lhc = inst_dict.get("last_health_check")
            if lhc is None:
                return "<span style='color:#6b7280'>—</span>"
            age = time.time() - lhc
            return f"<span style='color:#94a3b8'>{age:.0f}s ago</span>"

        cards_html = ""
        for s in servers:
            color = status_color(s["status"])
            lhc_badge = latency_badge(s)
            cards_html += f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                        padding:20px;margin-bottom:16px;">
              <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
                <span style="width:12px;height:12px;border-radius:50%;
                             background:{color};display:inline-block;
                             box-shadow:0 0 6px {color};"></span>
                <span style="font-size:1.1rem;font-weight:600;color:#f1f5f9;">
                  {s['tag']}
                </span>
                <span style="margin-left:auto;font-size:0.78rem;
                             background:#0f172a;border-radius:4px;
                             padding:2px 8px;color:{color};">
                  {s['status'].upper()}
                </span>
              </div>
              <table style="width:100%;font-size:0.82rem;color:#94a3b8;border-collapse:collapse;">
                <tr>
                  <td style="padding:3px 0;width:120px;">GPU</td>
                  <td style="color:#e2e8f0;">GPU{s['gpu_id']}</td>
                  <td style="padding:3px 0;width:120px;">Port</td>
                  <td style="color:#e2e8f0;">{s['port']}</td>
                </tr>
                <tr>
                  <td style="padding:3px 0;">Checkpoint</td>
                  <td colspan="3" style="color:#e2e8f0;font-size:0.76rem;
                                         word-break:break-all;">
                    {s['checkpoint_path']}
                  </td>
                </tr>
                <tr>
                  <td style="padding:3px 0;">Restarts</td>
                  <td style="color:#e2e8f0;">{s['restart_count']} / {MAX_RESTARTS}</td>
                  <td style="padding:3px 0;">Requests</td>
                  <td style="color:#e2e8f0;">{s['requests_served']}</td>
                </tr>
                <tr>
                  <td style="padding:3px 0;">Last check</td>
                  <td colspan="3">{lhc_badge}</td>
                </tr>
              </table>
            </div>
            """

        n_healthy = sum(1 for s in servers if s["status"] == "healthy")
        banner_color = "#22c55e" if n_healthy == len(servers) else (
            "#f59e0b" if n_healthy > 0 else "#ef4444"
        )
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — Server Manager</title>
  <meta http-equiv="refresh" content="15"/>
  <style>
    * {{ box-sizing:border-box; }}
    body {{ margin:0;padding:24px;background:#0f172a;color:#f1f5f9;
           font-family:'Inter',system-ui,sans-serif;min-height:100vh; }}
    h1 {{ font-size:1.4rem;font-weight:700;margin:0 0 4px;color:#f8fafc; }}
    .subtitle {{ font-size:0.82rem;color:#64748b;margin-bottom:24px; }}
    .banner {{ display:inline-flex;align-items:center;gap:8px;
               background:#1e293b;border:1px solid #334155;
               border-radius:8px;padding:10px 18px;margin-bottom:20px;
               font-size:0.88rem; }}
    .dot {{ width:10px;height:10px;border-radius:50%;background:{banner_color};
            box-shadow:0 0 6px {banner_color}; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Server Manager</h1>
  <p class="subtitle">Auto-refreshes every 15s &nbsp;·&nbsp; Proxy port {PROXY_PORT}</p>
  <div class="banner">
    <span class="dot"></span>
    <span>{n_healthy} / {len(servers)} servers healthy</span>
  </div>
  <div>
    {cards_html if cards_html else
     '<p style="color:#64748b;">No servers registered.</p>'}
  </div>
</body>
</html>"""
        return html

    return app


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_status(manager: ServerManager) -> None:
    servers = manager.list_servers()
    if not servers:
        print("No servers registered.")
        return
    col = {
        "healthy": "\033[92m",
        "unhealthy": "\033[91m",
        "starting": "\033[93m",
        "stopped": "\033[90m",
    }
    reset = "\033[0m"
    fmt = "{tag:<20} {status:<12} {gpu:<6} {port:<8} {restarts:<10} {requests}"
    print(fmt.format(
        tag="TAG", status="STATUS", gpu="GPU",
        port="PORT", restarts="RESTARTS", requests="REQUESTS",
    ))
    print("-" * 72)
    for s in servers:
        c = col.get(s["status"], "")
        print(fmt.format(
            tag=s["tag"],
            status=c + s["status"] + reset,
            gpu=f"GPU{s['gpu_id']}",
            port=str(s["port"]),
            restarts=f"{s['restart_count']}/{MAX_RESTARTS}",
            requests=str(s["requests_served"]),
        ))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T inference server lifecycle manager for OCI Robot Cloud"
    )
    parser.add_argument("--mock", action="store_true",
                        help="Use mock mode (3 simulated servers)")
    parser.add_argument("--serve", action="store_true",
                        help="Start the FastAPI proxy server")
    parser.add_argument("--port", type=int, default=PROXY_PORT,
                        help=f"Proxy server port (default: {PROXY_PORT})")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH),
                        help="Path to state JSON file")

    subparsers = parser.add_subparsers(dest="command")

    # register
    reg_p = subparsers.add_parser("register", help="Register a checkpoint")
    reg_p.add_argument("--checkpoint", required=True, help="Path to checkpoint directory")
    reg_p.add_argument("--tag", required=True, help="Unique name for this server")
    reg_p.add_argument("--gpu", type=int, required=True, dest="gpu_id",
                       help="GPU index (CUDA_VISIBLE_DEVICES)")
    reg_p.add_argument("--port", type=int, default=None, help="Override port (default: auto)")

    # start
    start_p = subparsers.add_parser("start", help="Start a registered server")
    start_p.add_argument("tag", help="Server tag")

    # stop
    stop_p = subparsers.add_parser("stop", help="Stop a running server")
    stop_p.add_argument("tag", help="Server tag")

    # status
    subparsers.add_parser("status", help="Print status of all servers")

    # start-all
    subparsers.add_parser("start-all", help="Start all registered servers")

    # stop-all
    subparsers.add_parser("stop-all", help="Stop all running servers")

    args = parser.parse_args()

    manager = ServerManager(mock=args.mock, state_path=Path(args.state))

    # ── --serve mode ──────────────────────────────────────────────────────────
    if args.serve:
        manager.start_monitor()
        app = build_app(manager)
        log.info("Starting proxy on port %d (mock=%s)", args.port, args.mock)
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
        return

    # ── Subcommands ───────────────────────────────────────────────────────────
    if args.command == "register":
        inst = manager.register(
            checkpoint_path=args.checkpoint,
            tag=args.tag,
            gpu_id=args.gpu_id,
            port=args.port,
        )
        print(f"Registered '{inst.tag}' → GPU{inst.gpu_id} port {inst.port}")
        return

    if args.command == "start":
        inst = manager.start(args.tag)
        print(f"Server '{inst.tag}' status: {inst.status}")
        return

    if args.command == "stop":
        inst = manager.stop(args.tag)
        print(f"Server '{inst.tag}' stopped.")
        return

    if args.command == "status" or args.command is None:
        _print_status(manager)
        return

    if args.command == "start-all":
        manager.start_all()
        _print_status(manager)
        return

    if args.command == "stop-all":
        manager.stop_all()
        _print_status(manager)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
