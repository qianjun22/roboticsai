"""
OCI Robot Cloud — Latency Profiler (port 8107)
Oracle Confidential
Profiles inference latency for GR00T model across pipeline stages.
"""
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random, math, datetime, json

STAGES = [
    {"name": "image_preprocess",      "mean": 12.4,  "std": 1.2,  "seed": 101},
    {"name": "tokenize_instruction",  "mean": 3.1,   "std": 0.4,  "seed": 102},
    {"name": "vit_encoder",           "mean": 48.7,  "std": 4.1,  "seed": 103},
    {"name": "llm_backbone",          "mean": 142.3, "std": 11.2, "seed": 104},
    {"name": "action_decoder",        "mean": 19.6,  "std": 2.3,  "seed": 105},
]

SLA_P99_TOTAL_MS = 300.0
N_SAMPLES = 100


def _percentile(data, p):
    s = sorted(data)
    idx = (len(s) - 1) * p / 100.0
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (idx - lo) * (s[hi] - s[lo])


def _generate_samples(stage):
    rng = random.Random(stage["seed"])
    return [max(0.1, rng.gauss(stage["mean"], stage["std"])) for _ in range(N_SAMPLES)]


def profile_stages():
    results = []
    for s in STAGES:
        samples = _generate_samples(s)
        p50 = _percentile(samples, 50)
        p90 = _percentile(samples, 90)
        p95 = _percentile(samples, 95)
        p99 = _percentile(samples, 99)
        mn = sum(samples) / len(samples)
        mx = max(samples)
        warn = p99 > 2 * mn
        results.append({
            "stage": s["name"],
            "p50": round(p50, 2),
            "p90": round(p90, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "mean": round(mn, 2),
            "max": round(mx, 2),
            "warning": warn,
        })
    return results


def sla_check():
    stages = profile_stages()
    total_p99 = sum(s["p99"] for s in stages)
    total_mean = sum(s["mean"] for s in stages)
    pass_fail = "PASS" if total_p99 < SLA_P99_TOTAL_MS else "FAIL"
    warned = [s["stage"] for s in stages if s["warning"]]
    return {
        "total_mean_ms": round(total_mean, 2),
        "total_p99_ms": round(total_p99, 2),
        "sla_threshold_ms": SLA_P99_TOTAL_MS,
        "sla_result": pass_fail,
        "stage_warnings": warned,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def build_svg(stages):
    W, H = 700, 250
    label_w = 180
    bar_area_w = W - label_w - 20
    n = len(stages)
    group_h = int((H - 50) / n)
    bar_h = 9
    gap = 4
    max_val = max(s["p99"] for s in stages) * 1.1 or 1

    def bx(v):
        return label_w + int(v / max_val * bar_area_w)

    parts = []
    for tick in [0, 50, 100, 150, 200, 250, 300]:
        tx = label_w + int(tick / max_val * bar_area_w)
        if tx > W - 10:
            break
        parts.append(f'<line x1="{tx}" y1="16" x2="{tx}" y2="{H-30}" stroke="#334155" stroke-width="1"/>')
        parts.append(f'<text x="{tx}" y="12" text-anchor="middle" fill="#64748b" font-size="9">{tick}ms</text>')

    for i, s in enumerate(stages):
        base_y = 20 + i * group_h
        parts.append(f'<text x="{label_w - 6}" y="{base_y + bar_h + 4}" text-anchor="end" fill="#cbd5e1" font-size="10">{s["stage"]}</text>')
        w50 = max(2, bx(s["p50"]) - label_w)
        parts.append(f'<rect x="{label_w}" y="{base_y}" width="{w50}" height="{bar_h}" rx="2" fill="#38bdf8" opacity="0.85"/>')
        parts.append(f'<text x="{label_w + w50 + 3}" y="{base_y + bar_h - 1}" fill="#38bdf8" font-size="8">{s["p50"]}</text>')
        w90 = max(2, bx(s["p90"]) - label_w)
        parts.append(f'<rect x="{label_w}" y="{base_y + bar_h + gap}" width="{w90}" height="{bar_h}" rx="2" fill="#f59e0b" opacity="0.75"/>')
        parts.append(f'<text x="{label_w + w90 + 3}" y="{base_y + bar_h*2 + gap - 1}" fill="#f59e0b" font-size="8">{s["p90"]}</text>')
        w99 = max(2, bx(s["p99"]) - label_w)
        parts.append(f'<rect x="{label_w}" y="{base_y + (bar_h + gap)*2}" width="{w99}" height="{bar_h}" rx="2" fill="#C74634" opacity="0.9"/>')
        parts.append(f'<text x="{label_w + w99 + 3}" y="{base_y + (bar_h+gap)*2 + bar_h - 1}" fill="#C74634" font-size="8">{s["p99"]}</text>')

    sla_x = label_w + int(300 / max_val * bar_area_w)
    if sla_x < W - 5:
        parts.append(f'<line x1="{sla_x}" y1="16" x2="{sla_x}" y2="{H-30}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,3"/>')
        parts.append(f'<text x="{sla_x + 2}" y="25" fill="#ef4444" font-size="9">SLA 300ms</text>')

    legend_y = H - 20
    parts.append(f'<rect x="4" y="{legend_y}" width="10" height="8" rx="2" fill="#38bdf8"/>')
    parts.append(f'<text x="18" y="{legend_y+8}" fill="#94a3b8" font-size="9">p50</text>')
    parts.append(f'<rect x="50" y="{legend_y}" width="10" height="8" rx="2" fill="#f59e0b"/>')
    parts.append(f'<text x="64" y="{legend_y+8}" fill="#94a3b8" font-size="9">p90</text>')
    parts.append(f'<rect x="96" y="{legend_y}" width="10" height="8" rx="2" fill="#C74634"/>')
    parts.append(f'<text x="110" y="{legend_y+8}" fill="#94a3b8" font-size="9">p99</text>')

    svg_body = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">{svg_body}</svg>'
    )


def build_html():
    stages = profile_stages()
    sla = sla_check()
    svg = build_svg(stages)

    sla_color = "#22c55e" if sla["sla_result"] == "PASS" else "#ef4444"

    rows = []
    for s in stages:
        warn_tag = ' <span style="color:#f59e0b;font-size:11px">&#9888; p99 &gt; 2&#215;mean</span>' if s["warning"] else ""
        rows.append(
            f'<tr><td>{s["stage"]}{warn_tag}</td>'
            f'<td>{s["mean"]}</td><td>{s["p50"]}</td><td>{s["p90"]}</td>'
            f'<td>{s["p95"]}</td><td style="color:#C74634;font-weight:700">{s["p99"]}</td>'
            f'<td>{s["max"]}</td></tr>'
        )
    table_rows = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Latency Profiler — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:24px}}
  h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:12px;margin-bottom:20px}}
  .cards{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .card{{background:#1e293b;border-radius:8px;padding:16px 24px;min-width:130px}}
  .card .val{{font-size:26px;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;color:#38bdf8;font-size:12px;padding:10px 12px;text-align:left}}
  td{{padding:9px 12px;font-size:13px;border-bottom:1px solid #0f172a}}
  tr:last-child td{{border-bottom:none}}
  .section{{margin-bottom:24px}}
  .section h2{{color:#C74634;font-size:15px;margin-bottom:10px}}
  .foot{{margin-top:32px;font-size:11px;color:#334155;text-align:center}}
  .sla-badge{{display:inline-block;padding:3px 12px;border-radius:12px;font-weight:700;font-size:14px;color:{sla_color};border:1.5px solid {sla_color}}}
</style></head><body>
<h1>Latency Profiler</h1>
<div class="sub">OCI Robot Cloud — GR00T Pipeline Stages &nbsp;|&nbsp; {sla["generated_at"]}</div>
<div class="cards">
  <div class="card"><div class="val">{sla["total_mean_ms"]}<span style="font-size:14px">ms</span></div><div class="lbl">Total Mean</div></div>
  <div class="card"><div class="val" style="color:#C74634">{sla["total_p99_ms"]}<span style="font-size:14px">ms</span></div><div class="lbl">Total p99</div></div>
  <div class="card"><div class="val">{SLA_P99_TOTAL_MS:.0f}<span style="font-size:14px">ms</span></div><div class="lbl">SLA Threshold</div></div>
  <div class="card"><div class="val"><span class="sla-badge">{sla["sla_result"]}</span></div><div class="lbl">SLA Status</div></div>
  <div class="card"><div class="val">{N_SAMPLES}</div><div class="lbl">Samples/Stage</div></div>
</div>
<div class="section"><h2>Latency Breakdown (p50 / p90 / p99)</h2>{svg}</div>
<div class="section"><h2>Stage Statistics (ms)</h2>
<table><thead><tr><th>Stage</th><th>Mean</th><th>p50</th><th>p90</th><th>p95</th><th>p99</th><th>Max</th></tr></thead>
<tbody>{table_rows}</tbody></table></div>
<div class="foot">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud Latency Profiler &nbsp;|&nbsp; Port 8107</div>
</body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="Latency Profiler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def root():
        return build_html()

    @app.get("/profile")
    def profile():
        stages = profile_stages()
        sla = sla_check()
        return JSONResponse({"stages": stages, "sla": sla})

    @app.get("/stages")
    def stages():
        return JSONResponse(profile_stages())

    @app.get("/sla")
    def sla():
        return JSONResponse(sla_check())

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "latency_profiler", "port": 8107}


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("latency_profiler:app", host="0.0.0.0", port=8107, reload=False)
    else:
        html = build_html()
        out = "/tmp/latency_profile.html"
        with open(out, "w") as f:
            f.write(html)
        print(f"Saved to {out}")
        print(json.dumps(sla_check(), indent=2))
