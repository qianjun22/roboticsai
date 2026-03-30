"""
OCI Robot Cloud — Config Drift Detector (port 8106)
Oracle Confidential
Detects configuration drift between deployed GR00T model configs and the golden reference.
"""
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import hashlib, datetime, json

GOLDEN = {
    "model": "dagger_run9_v2.2",
    "chunk_size": 16,
    "lora_rank": 16,
    "batch_size": 4,
    "temperature": 0.1,
    "fp16": True,
}

INSTANCES = [
    {"id": "ashburn-prod-1",     "host": "138.1.153.110",  "model": "dagger_run9_v2.2", "chunk_size": 24, "lora_rank": 16, "batch_size": 4,  "temperature": 0.1,  "fp16": True},
    {"id": "ashburn-prod-2",     "host": "138.1.153.111",  "model": "dagger_run9_v2.2", "chunk_size": 16, "lora_rank": 16, "batch_size": 4,  "temperature": 0.1,  "fp16": True},
    {"id": "ashburn-canary-1",   "host": "138.1.153.112",  "model": "groot_finetune_v2","chunk_size": 16, "lora_rank": 16, "batch_size": 4,  "temperature": 0.15, "fp16": True},
    {"id": "phoenix-eval-1",     "host": "129.213.44.22",  "model": "dagger_run9_v2.2", "chunk_size": 16, "lora_rank": 16, "batch_size": 4,  "temperature": 0.1,  "fp16": False},
    {"id": "frankfurt-staging-1","host": "130.61.81.44",   "model": "groot_finetune_v2","chunk_size": 16, "lora_rank": 16, "batch_size": 4,  "temperature": 0.1,  "fp16": True},
    {"id": "ashburn-shadow-1",   "host": "138.1.153.113",  "model": "dagger_run9_v2.2", "chunk_size": 8,  "lora_rank": 8,  "batch_size": 8,  "temperature": 0.1,  "fp16": True},
]

CONFIG_KEYS = ["model", "chunk_size", "lora_rank", "batch_size", "temperature", "fp16"]


def detect_drift():
    results = []
    for inst in INSTANCES:
        drifted = []
        details = {}
        for k in CONFIG_KEYS:
            if inst.get(k) != GOLDEN.get(k):
                drifted.append(k)
                details[k] = {"actual": inst.get(k), "expected": GOLDEN.get(k)}
        n = len(drifted)
        severity = "CLEAN" if n == 0 else ("CRITICAL" if n > 2 else "WARNING")
        results.append({
            "instance_id": inst["id"],
            "host": inst["host"],
            "drifted_keys": drifted,
            "drift_details": details,
            "severity": severity,
        })
    return results


def drift_summary():
    results = detect_drift()
    counts = {"CLEAN": 0, "WARNING": 0, "CRITICAL": 0}
    drifted_instances = []
    for r in results:
        counts[r["severity"]] += 1
        if r["severity"] != "CLEAN":
            drifted_instances.append(r["instance_id"])
    return {
        "total": len(results),
        "clean": counts["CLEAN"],
        "warning": counts["WARNING"],
        "critical": counts["CRITICAL"],
        "drifted_instances": drifted_instances,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def build_svg():
    W, H = 600, 200
    col_w = 80
    row_h = 26
    label_w = 160
    off_x = label_w
    off_y = 40

    drifts = detect_drift()
    drift_map = {r["instance_id"]: set(r["drifted_keys"]) for r in drifts}

    cells = []
    for ci, key in enumerate(CONFIG_KEYS):
        cx = off_x + ci * col_w + col_w // 2
        cells.append(f'<text x="{cx}" y="28" text-anchor="middle" fill="#94a3b8" font-size="10">{key}</text>')

    for ri, inst in enumerate(INSTANCES):
        iy = off_y + ri * row_h
        sev = next(r["severity"] for r in drifts if r["instance_id"] == inst["id"])
        sev_color = {"CLEAN": "#22c55e", "WARNING": "#f59e0b", "CRITICAL": "#ef4444"}[sev]
        cells.append(f'<text x="4" y="{iy + 17}" fill="#cbd5e1" font-size="10">{inst["id"]}</text>')
        cells.append(f'<rect x="{label_w - 12}" y="{iy + 5}" width="8" height="14" rx="2" fill="{sev_color}"/>')
        for ci, key in enumerate(CONFIG_KEYS):
            cx = off_x + ci * col_w
            color = "#ef4444" if key in drift_map.get(inst["id"], set()) else "#22c55e"
            cells.append(f'<rect x="{cx + 2}" y="{iy + 3}" width="{col_w - 4}" height="{row_h - 5}" rx="3" fill="{color}" opacity="0.85"/>')

    body = "\n".join(cells)
    legend = (
        f'<rect x="4" y="{H-18}" width="12" height="10" rx="2" fill="#22c55e"/>'
        f'<text x="20" y="{H-9}" fill="#94a3b8" font-size="9">MATCH</text>'
        f'<rect x="70" y="{H-18}" width="12" height="10" rx="2" fill="#ef4444"/>'
        f'<text x="86" y="{H-9}" fill="#94a3b8" font-size="9">DRIFT</text>'
        f'<rect x="130" y="{H-18}" width="8" height="10" rx="2" fill="#f59e0b"/>'
        f'<text x="142" y="{H-9}" fill="#94a3b8" font-size="9">WARNING</text>'
        f'<rect x="210" y="{H-18}" width="8" height="10" rx="2" fill="#ef4444"/>'
        f'<text x="222" y="{H-9}" fill="#94a3b8" font-size="9">CRITICAL</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{body}{legend}</svg>'
    )


def build_html():
    summary = drift_summary()
    drift_data = detect_drift()
    svg = build_svg()

    rows = []
    for r in drift_data:
        sev_color = {"CLEAN": "#22c55e", "WARNING": "#f59e0b", "CRITICAL": "#ef4444"}[r["severity"]]
        detail_str = "; ".join(
            f"{k}: {v['actual']} (exp {v['expected']})" for k, v in r["drift_details"].items()
        ) or "—"
        rows.append(
            f'<tr><td>{r["instance_id"]}</td><td>{r["host"]}</td>'
            f'<td style="color:{sev_color};font-weight:700">{r["severity"]}</td>'
            f'<td style="font-size:12px;color:#94a3b8">{detail_str}</td></tr>'
        )
    table_rows = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Config Drift Detector — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:24px}}
  h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:12px;margin-bottom:20px}}
  .cards{{display:flex;gap:16px;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:8px;padding:16px 24px;min-width:120px}}
  .card .val{{font-size:28px;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  .card .val.warn{{color:#f59e0b}}.card .val.crit{{color:#ef4444}}.card .val.ok{{color:#22c55e}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;color:#38bdf8;font-size:12px;padding:10px 12px;text-align:left}}
  td{{padding:9px 12px;font-size:13px;border-bottom:1px solid #0f172a}}
  tr:last-child td{{border-bottom:none}}
  .section{{margin-bottom:24px}}
  .section h2{{color:#C74634;font-size:15px;margin-bottom:10px}}
  .foot{{margin-top:32px;font-size:11px;color:#334155;text-align:center}}
</style></head><body>
<h1>Config Drift Detector</h1>
<div class="sub">OCI Robot Cloud — Golden Reference: {json.dumps(GOLDEN)} &nbsp;|&nbsp; {summary["generated_at"]}</div>
<div class="cards">
  <div class="card"><div class="val">{summary["total"]}</div><div class="lbl">Instances</div></div>
  <div class="card"><div class="val ok">{summary["clean"]}</div><div class="lbl">Clean</div></div>
  <div class="card"><div class="val warn">{summary["warning"]}</div><div class="lbl">Warning</div></div>
  <div class="card"><div class="val crit">{summary["critical"]}</div><div class="lbl">Critical</div></div>
</div>
<div class="section"><h2>Config Heatmap</h2>{svg}</div>
<div class="section"><h2>Drift Details</h2>
<table><thead><tr><th>Instance</th><th>Host</th><th>Severity</th><th>Drift Details</th></tr></thead>
<tbody>{table_rows}</tbody></table></div>
<div class="foot">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud Config Drift Detector &nbsp;|&nbsp; Port 8106</div>
</body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="Config Drift Detector", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def root():
        return build_html()

    @app.get("/drift")
    def drift():
        return JSONResponse(detect_drift())

    @app.get("/summary")
    def summary():
        return JSONResponse(drift_summary())

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "config_drift_detector", "port": 8106}


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("config_drift_detector:app", host="0.0.0.0", port=8106, reload=False)
    else:
        html = build_html()
        out = "/tmp/config_drift_report.html"
        with open(out, "w") as f:
            f.write(html)
        print(f"Saved to {out}")
        s = drift_summary()
        print(json.dumps(s, indent=2))
