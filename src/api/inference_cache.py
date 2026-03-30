"""
inference_cache.py — GR00T Inference Result Cache (port 8009)

Speeds up evaluation loops by caching state→action predictions in SQLite.
Cache key = SHA256(flattened joint_states + image_hash).
"""

import argparse
import hashlib
import json
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = "/tmp/groot_inference_cache.db"
DEFAULT_PORT = 8009
DEFAULT_SOURCE_URL = "http://localhost:8002/predict"
TTL_SECONDS = 86400          # 24 hours
MAX_ENTRIES = 10_000
MOCK_SEED_COUNT = 200

# ---------------------------------------------------------------------------
# Cache backend
# ---------------------------------------------------------------------------

class InferenceCache:
    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._total_hits = 0
        self._total_misses = 0
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inference_cache (
                    key              TEXT PRIMARY KEY,
                    action_json      TEXT NOT NULL,
                    hit_count        INTEGER NOT NULL DEFAULT 0,
                    latency_saved_ms REAL NOT NULL DEFAULT 0.0,
                    created_at       TEXT NOT NULL,
                    last_hit_at      TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created ON inference_cache(created_at)"
            )

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(joint_states: list, image_b64: Optional[str] = None) -> str:
        payload = ",".join(f"{v:.6f}" for v in joint_states)
        if image_b64:
            # Use first 16 bytes of raw image data for the hash component
            raw_bytes = image_b64.encode("ascii")[:16]
            image_hash = raw_bytes.hex()
            payload += f"|{image_hash}"
        return hashlib.sha256(payload.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def lookup(self, key: str) -> Optional[dict]:
        """Return cached action dict or None (also handles TTL expiry)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cutoff = datetime.fromtimestamp(
            time.time() - TTL_SECONDS, tz=timezone.utc
        ).isoformat()

        with self._conn() as conn:
            row = conn.execute(
                "SELECT action_json, latency_saved_ms FROM inference_cache "
                "WHERE key = ? AND created_at > ?",
                (key, cutoff),
            ).fetchone()

            if row is None:
                self._total_misses += 1
                return None

            # Update hit tracking
            conn.execute(
                "UPDATE inference_cache "
                "SET hit_count = hit_count + 1, last_hit_at = ? "
                "WHERE key = ?",
                (now_iso, key),
            )
            self._total_hits += 1
            return json.loads(row["action_json"])

    def store(self, key: str, action: dict, latency_ms: float = 0.0) -> None:
        """Insert or replace a cache entry, evicting LRU entries if over limit."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM inference_cache"
            ).fetchone()[0]

            if count >= MAX_ENTRIES:
                # LRU eviction: remove oldest 5% of entries
                evict_n = max(1, MAX_ENTRIES // 20)
                conn.execute(
                    "DELETE FROM inference_cache WHERE key IN ("
                    "  SELECT key FROM inference_cache"
                    "  ORDER BY last_hit_at ASC LIMIT ?"
                    ")",
                    (evict_n,),
                )

            conn.execute(
                "INSERT OR REPLACE INTO inference_cache "
                "(key, action_json, hit_count, latency_saved_ms, created_at, last_hit_at) "
                "VALUES (?, ?, 0, ?, ?, ?)",
                (key, json.dumps(action), latency_ms, now_iso, now_iso),
            )

    def stats(self) -> dict:
        cutoff = datetime.fromtimestamp(
            time.time() - TTL_SECONDS, tz=timezone.utc
        ).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt, "
                "       SUM(hit_count) as total_hits_db, "
                "       SUM(latency_saved_ms * hit_count) as total_latency "
                "FROM inference_cache WHERE created_at > ?",
                (cutoff,),
            ).fetchone()

        total_requests = self._total_hits + self._total_misses
        hit_rate = self._total_hits / total_requests if total_requests > 0 else 0.0

        return {
            "total_entries": row["cnt"] or 0,
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "latency_saved_ms": round(row["total_latency"] or 0.0, 2),
            "hit_rate": round(hit_rate, 4),
        }

    def top_entries(self, n: int = 10) -> list:
        cutoff = datetime.fromtimestamp(
            time.time() - TTL_SECONDS, tz=timezone.utc
        ).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT key, hit_count, latency_saved_ms, last_hit_at "
                "FROM inference_cache WHERE created_at > ? "
                "ORDER BY hit_count DESC LIMIT ?",
                (cutoff, n),
            ).fetchall()
        return [dict(r) for r in rows]

    def clear(self) -> int:
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM inference_cache").fetchone()[0]
            conn.execute("DELETE FROM inference_cache")
        self._total_hits = 0
        self._total_misses = 0
        return count

    def seed_mock(self, n: int = MOCK_SEED_COUNT) -> None:
        """Pre-seed cache with synthetic entries for testing/demo."""
        rng = random.Random(42)
        for i in range(n):
            joint_states = [rng.uniform(-1.5, 1.5) for _ in range(9)]
            action = {
                "joint_positions": [rng.uniform(-1.0, 1.0) for _ in range(9)],
                "gripper": rng.uniform(0.0, 1.0),
            }
            key = self.make_key(joint_states)
            latency = rng.uniform(80.0, 350.0)
            self.store(key, action, latency)
            # Simulate some hits
            hits = rng.randint(0, 20)
            if hits > 0:
                now_iso = datetime.now(timezone.utc).isoformat()
                with self._conn() as conn:
                    conn.execute(
                        "UPDATE inference_cache SET hit_count = ?, last_hit_at = ? WHERE key = ?",
                        (hits, now_iso, key),
                    )
                self._total_hits += hits


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

cache: Optional[InferenceCache] = None

if HAS_FASTAPI:
    app = FastAPI(title="GR00T Inference Cache", version="1.0.0")

    class InferRequest(BaseModel):
        joint_states: list
        image_b64: Optional[str] = None
        source_url: Optional[str] = DEFAULT_SOURCE_URL

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "inference_cache", "port": DEFAULT_PORT}

    @app.get("/api/stats")
    def api_stats():
        return cache.stats()

    @app.delete("/api/clear")
    def api_clear():
        n = cache.clear()
        return {"cleared": n, "status": "ok"}

    @app.post("/infer")
    async def infer(req: InferRequest):
        t0 = time.time()

        if not req.joint_states or len(req.joint_states) != 9:
            raise HTTPException(status_code=422, detail="joint_states must be a list of 9 floats")

        key = cache.make_key(req.joint_states, req.image_b64)
        cached = cache.lookup(key)
        elapsed_ms = (time.time() - t0) * 1000

        if cached is not None:
            return {"action": cached, "cache_hit": True, "latency_ms": round(elapsed_ms, 2)}

        # Cache miss — proxy to source
        source = req.source_url or DEFAULT_SOURCE_URL
        proxy_t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"joint_states": req.joint_states}
                if req.image_b64:
                    payload["image_b64"] = req.image_b64
                resp = await client.post(source, json=payload)
                resp.raise_for_status()
                action = resp.json()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Upstream error: {exc}")

        proxy_ms = (time.time() - proxy_t0) * 1000
        cache.store(key, action, proxy_ms)

        total_ms = (time.time() - t0) * 1000
        return {"action": action, "cache_hit": False, "latency_ms": round(total_ms, 2)}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        s = cache.stats()
        top = cache.top_entries(10)

        rows_html = ""
        for i, entry in enumerate(top, 1):
            short_key = entry["key"][:16] + "..."
            rows_html += (
                f"<tr>"
                f"<td>{i}</td>"
                f"<td style='font-family:monospace;font-size:12px'>{short_key}</td>"
                f"<td>{entry['hit_count']}</td>"
                f"<td>{entry['latency_saved_ms']:.1f}</td>"
                f"<td>{entry['last_hit_at'][:19]}</td>"
                f"</tr>"
            )

        hit_rate_pct = f"{s['hit_rate'] * 100:.1f}%"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GR00T Inference Cache</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ font-size: 24px; font-weight: 700; color: #38bdf8; margin-bottom: 8px; }}
    .subtitle {{ color: #64748b; font-size: 14px; margin-bottom: 32px; }}
    .cards {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 36px; }}
    .card {{ background: #1e293b; border-radius: 12px; padding: 20px 28px; min-width: 160px; }}
    .card .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .card .value {{ font-size: 32px; font-weight: 700; color: #f1f5f9; }}
    .card .value.green {{ color: #4ade80; }}
    .card .value.blue  {{ color: #38bdf8; }}
    .card .value.amber {{ color: #fbbf24; }}
    h2 {{ font-size: 16px; color: #94a3b8; margin-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }}
    th {{ text-align: left; padding: 12px 16px; font-size: 12px; color: #64748b; text-transform: uppercase; background: #0f172a; }}
    td {{ padding: 10px 16px; font-size: 13px; border-top: 1px solid #0f172a; }}
    tr:hover td {{ background: #263043; }}
    .badge {{ display: inline-block; background: #0ea5e9; color: #fff; font-size: 11px; border-radius: 4px; padding: 2px 6px; margin-left: 8px; }}
    .footer {{ margin-top: 40px; font-size: 12px; color: #334155; }}
  </style>
  <meta http-equiv="refresh" content="10">
</head>
<body>
  <h1>GR00T Inference Cache <span class="badge">port 8009</span></h1>
  <p class="subtitle">SQLite-backed prediction cache — auto-refreshes every 10s</p>

  <div class="cards">
    <div class="card">
      <div class="label">Hit Rate</div>
      <div class="value green">{hit_rate_pct}</div>
    </div>
    <div class="card">
      <div class="label">Latency Saved</div>
      <div class="value blue">{s['latency_saved_ms']:.0f} ms</div>
    </div>
    <div class="card">
      <div class="label">Cache Entries</div>
      <div class="value">{s['total_entries']:,}</div>
    </div>
    <div class="card">
      <div class="label">Total Hits</div>
      <div class="value amber">{s['total_hits']:,}</div>
    </div>
    <div class="card">
      <div class="label">Total Misses</div>
      <div class="value">{s['total_misses']:,}</div>
    </div>
  </div>

  <h2>Top 10 Most-Hit Entries</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Key (truncated)</th><th>Hits</th><th>Latency Saved (ms)</th><th>Last Hit</th>
      </tr>
    </thead>
    <tbody>
      {rows_html if rows_html else '<tr><td colspan="5" style="color:#475569;text-align:center;padding:24px">No entries yet</td></tr>'}
    </tbody>
  </table>

  <p class="footer">TTL: 24h &nbsp;|&nbsp; Max entries: 10,000 (LRU eviction) &nbsp;|&nbsp; DB: {cache.db_path}</p>
</body>
</html>"""
        return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GR00T Inference Cache Service (port 8009)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite DB path")
    parser.add_argument("--mock", action="store_true", help="Pre-seed with 200 synthetic cache entries")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("ERROR: FastAPI / httpx not installed. Run: pip install fastapi uvicorn httpx")
        raise SystemExit(1)

    global cache
    cache = InferenceCache(db_path=args.db)

    if args.mock:
        print(f"Seeding {MOCK_SEED_COUNT} synthetic cache entries...")
        cache.seed_mock(MOCK_SEED_COUNT)
        print(f"Done. Stats: {cache.stats()}")

    import uvicorn
    print(f"Starting GR00T Inference Cache on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
