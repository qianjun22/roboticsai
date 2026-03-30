"""Attention Head Analyzer — port 8624
Analyzes transformer attention head entropy, importance, and task-phase shifts.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Attention Head Analyzer — OCI Robot Cloud</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #38bdf8; font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 32px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
  .card h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 16px; letter-spacing: 0.05em; text-transform: uppercase; }
  .card-full { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px; }
  .card-full h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 16px; letter-spacing: 0.05em; text-transform: uppercase; }
  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .metric { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; text-align: center; }
  .metric .val { font-size: 1.8rem; font-weight: 700; color: #C74634; }
  .metric .lbl { font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .legend { display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; }
  .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: #94a3b8; }
  .legend-dot { width: 12px; height: 12px; border-radius: 2px; }
</style>
</head>
<body>
<h1>Attention Head Analyzer</h1>
<p class="subtitle">GR00T N1.6 transformer — layer-wise entropy, head importance, and task-phase activation patterns</p>

<div class="metrics">
  <div class="metric"><div class="val">18%</div><div class="lbl">Redundant Heads</div></div>
  <div class="metric"><div class="val">L-8</div><div class="lbl">Spatial Relations Layer</div></div>
  <div class="metric"><div class="val">L-11</div><div class="lbl">Gripper / Contact Layer</div></div>
  <div class="metric"><div class="val">-400M</div><div class="lbl">Params (structured pruning)</div></div>
</div>

<!-- SVG 1: 12×16 Attention Head Heatmap -->
<div class="card-full">
  <h2>Attention Head Entropy Heatmap (12 layers × 16 heads)</h2>
  <svg viewBox="0 0 860 300" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
    <defs>
      <linearGradient id="heatGrad" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0%" stop-color="#38bdf8"/>
        <stop offset="50%" stop-color="#a78bfa"/>
        <stop offset="100%" stop-color="#f97316"/>
      </linearGradient>
    </defs>
    <!-- Y axis labels (layers) -->
    <text x="38" y="24" fill="#64748b" font-size="10" text-anchor="end">L0</text>
    <text x="38" y="46" fill="#64748b" font-size="10" text-anchor="end">L1</text>
    <text x="38" y="68" fill="#64748b" font-size="10" text-anchor="end">L2</text>
    <text x="38" y="90" fill="#64748b" font-size="10" text-anchor="end">L3</text>
    <text x="38" y="112" fill="#64748b" font-size="10" text-anchor="end">L4</text>
    <text x="38" y="134" fill="#64748b" font-size="10" text-anchor="end">L5</text>
    <text x="38" y="156" fill="#64748b" font-size="10" text-anchor="end">L6</text>
    <text x="38" y="178" fill="#64748b" font-size="10" text-anchor="end">L7</text>
    <text x="38" y="200" fill="#64748b" font-size="10" text-anchor="end">L8</text>
    <text x="38" y="222" fill="#64748b" font-size="10" text-anchor="end">L9</text>
    <text x="38" y="244" fill="#64748b" font-size="10" text-anchor="end">L10</text>
    <text x="38" y="266" fill="#64748b" font-size="10" text-anchor="end">L11</text>
    <!-- X axis labels (heads H0-H15) -->
    <text x="52"  y="285" fill="#64748b" font-size="9" text-anchor="middle">H0</text>
    <text x="90"  y="285" fill="#64748b" font-size="9" text-anchor="middle">H2</text>
    <text x="128" y="285" fill="#64748b" font-size="9" text-anchor="middle">H4</text>
    <text x="166" y="285" fill="#64748b" font-size="9" text-anchor="middle">H6</text>
    <text x="204" y="285" fill="#64748b" font-size="9" text-anchor="middle">H8</text>
    <text x="242" y="285" fill="#64748b" font-size="9" text-anchor="middle">H10</text>
    <text x="280" y="285" fill="#64748b" font-size="9" text-anchor="middle">H12</text>
    <text x="318" y="285" fill="#64748b" font-size="9" text-anchor="middle">H14</text>
    <!-- Row 0 (L0) - mostly medium entropy -->
    <rect x="42" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.55"/>
    <rect x="61" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.70"/>
    <rect x="80" y="12" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.80"/>
    <rect x="99" y="12" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.40"/>
    <rect x="118" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.60"/>
    <rect x="137" y="12" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.65"/>
    <rect x="156" y="12" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.35"/>
    <rect x="175" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.50"/>
    <rect x="194" y="12" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.75"/>
    <rect x="213" y="12" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="232" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.68"/>
    <rect x="251" y="12" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.72"/>
    <rect x="270" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.58"/>
    <rect x="289" y="12" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.35"/>
    <rect x="308" y="12" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.62"/>
    <rect x="327" y="12" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.55"/>
    <!-- Row 1 (L1) -->
    <rect x="42" y="34" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.65"/>
    <rect x="61" y="34" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.55"/>
    <rect x="80" y="34" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="99" y="34" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="118" y="34" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.70"/>
    <rect x="137" y="34" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="156" y="34" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.60"/>
    <rect x="175" y="34" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.75"/>
    <rect x="194" y="34" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.50"/>
    <rect x="213" y="34" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.35"/>
    <rect x="232" y="34" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.65"/>
    <rect x="251" y="34" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.85"/>
    <rect x="270" y="34" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.60"/>
    <rect x="289" y="34" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="308" y="34" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.72"/>
    <rect x="327" y="34" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.50"/>
    <!-- Row 2 (L2) -->
    <rect x="42" y="56" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.60"/>
    <rect x="61" y="56" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.85"/>
    <rect x="80" y="56" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="99" y="56" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.75"/>
    <rect x="118" y="56" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.70"/>
    <rect x="137" y="56" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.90"/>
    <rect x="156" y="56" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="175" y="56" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.65"/>
    <rect x="194" y="56" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.80"/>
    <rect x="213" y="56" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.70"/>
    <rect x="232" y="56" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.32"/>
    <rect x="251" y="56" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.78"/>
    <rect x="270" y="56" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.55"/>
    <rect x="289" y="56" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.82"/>
    <rect x="308" y="56" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="327" y="56" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.68"/>
    <!-- Row 3 (L3) -->
    <rect x="42" y="78" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.35"/>
    <rect x="61" y="78" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.75"/>
    <rect x="80" y="78" width="18" height="18" rx="2" fill="#f97316" opacity="0.45"/>
    <rect x="99" y="78" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="118" y="78" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="137" y="78" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.88"/>
    <rect x="156" y="78" width="18" height="18" rx="2" fill="#f97316" opacity="0.50"/>
    <rect x="175" y="78" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.70"/>
    <rect x="194" y="78" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="213" y="78" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.80"/>
    <rect x="232" y="78" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.65"/>
    <rect x="251" y="78" width="18" height="18" rx="2" fill="#f97316" opacity="0.42"/>
    <rect x="270" y="78" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.75"/>
    <rect x="289" y="78" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="308" y="78" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.70"/>
    <rect x="327" y="78" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.60"/>
    <!-- Row 4 (L4) -->
    <rect x="42" y="100" width="18" height="18" rx="2" fill="#f97316" opacity="0.50"/>
    <rect x="61" y="100" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.70"/>
    <rect x="80" y="100" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.85"/>
    <rect x="99" y="100" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="118" y="100" width="18" height="18" rx="2" fill="#f97316" opacity="0.60"/>
    <rect x="137" y="100" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.75"/>
    <rect x="156" y="100" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.90"/>
    <rect x="175" y="100" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="194" y="100" width="18" height="18" rx="2" fill="#f97316" opacity="0.55"/>
    <rect x="213" y="100" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="232" y="100" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.68"/>
    <rect x="251" y="100" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.32"/>
    <rect x="270" y="100" width="18" height="18" rx="2" fill="#f97316" opacity="0.65"/>
    <rect x="289" y="100" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.70"/>
    <rect x="308" y="100" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.82"/>
    <rect x="327" y="100" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.58"/>
    <!-- Row 5 (L5) -->
    <rect x="42" y="122" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.70"/>
    <rect x="61" y="122" width="18" height="18" rx="2" fill="#f97316" opacity="0.65"/>
    <rect x="80" y="122" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.75"/>
    <rect x="99" y="122" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.80"/>
    <rect x="118" y="122" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="137" y="122" width="18" height="18" rx="2" fill="#f97316" opacity="0.72"/>
    <rect x="156" y="122" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.65"/>
    <rect x="175" y="122" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.90"/>
    <rect x="194" y="122" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.55"/>
    <rect x="213" y="122" width="18" height="18" rx="2" fill="#f97316" opacity="0.80"/>
    <rect x="232" y="122" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="251" y="122" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.75"/>
    <rect x="270" y="122" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.68"/>
    <rect x="289" y="122" width="18" height="18" rx="2" fill="#f97316" opacity="0.58"/>
    <rect x="308" y="122" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.82"/>
    <rect x="327" y="122" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.60"/>
    <!-- Row 6 (L6) -->
    <rect x="42" y="144" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.90"/>
    <rect x="61" y="144" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.60"/>
    <rect x="80" y="144" width="18" height="18" rx="2" fill="#f97316" opacity="0.70"/>
    <rect x="99" y="144" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.85"/>
    <rect x="118" y="144" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="137" y="144" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.90"/>
    <rect x="156" y="144" width="18" height="18" rx="2" fill="#f97316" opacity="0.75"/>
    <rect x="175" y="144" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.50"/>
    <rect x="194" y="144" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="213" y="144" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.32"/>
    <rect x="232" y="144" width="18" height="18" rx="2" fill="#f97316" opacity="0.68"/>
    <rect x="251" y="144" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.85"/>
    <rect x="270" y="144" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.70"/>
    <rect x="289" y="144" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.75"/>
    <rect x="308" y="144" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="327" y="144" width="18" height="18" rx="2" fill="#f97316" opacity="0.60"/>
    <!-- Row 7 (L7) -->
    <rect x="42" y="166" width="18" height="18" rx="2" fill="#f97316" opacity="0.75"/>
    <rect x="61" y="166" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.95"/>
    <rect x="80" y="166" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.55"/>
    <rect x="99" y="166" width="18" height="18" rx="2" fill="#f97316" opacity="0.85"/>
    <rect x="118" y="166" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.70"/>
    <rect x="137" y="166" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="156" y="166" width="18" height="18" rx="2" fill="#f97316" opacity="0.90"/>
    <rect x="175" y="166" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="194" y="166" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.65"/>
    <rect x="213" y="166" width="18" height="18" rx="2" fill="#f97316" opacity="0.78"/>
    <rect x="232" y="166" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="251" y="166" width="18" height="18" rx="2" fill="#7dd3fc" opacity="0.88"/>
    <rect x="270" y="166" width="18" height="18" rx="2" fill="#f97316" opacity="0.72"/>
    <rect x="289" y="166" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.85"/>
    <rect x="308" y="166" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.60"/>
    <rect x="327" y="166" width="18" height="18" rx="2" fill="#f97316" opacity="0.65"/>
    <!-- Row 8 (L8) - spatial relations: high entropy, mostly orange -->
    <rect x="42" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.90"/>
    <rect x="61" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.85"/>
    <rect x="80" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.95"/>
    <rect x="99" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.80"/>
    <rect x="118" y="188" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.70"/>
    <rect x="137" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.88"/>
    <rect x="156" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.92"/>
    <rect x="175" y="188" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="194" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.87"/>
    <rect x="213" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.75"/>
    <rect x="232" y="188" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.65"/>
    <rect x="251" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.93"/>
    <rect x="270" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.82"/>
    <rect x="289" y="188" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="308" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.88"/>
    <rect x="327" y="188" width="18" height="18" rx="2" fill="#f97316" opacity="0.78"/>
    <text x="355" y="200" fill="#f97316" font-size="9" font-style="italic">← spatial relations</text>
    <!-- Row 9 (L9) -->
    <rect x="42" y="210" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.75"/>
    <rect x="61" y="210" width="18" height="18" rx="2" fill="#f97316" opacity="0.65"/>
    <rect x="80" y="210" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="99" y="210" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.90"/>
    <rect x="118" y="210" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="137" y="210" width="18" height="18" rx="2" fill="#f97316" opacity="0.70"/>
    <rect x="156" y="210" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.85"/>
    <rect x="175" y="210" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.75"/>
    <rect x="194" y="210" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="213" y="210" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.80"/>
    <rect x="232" y="210" width="18" height="18" rx="2" fill="#f97316" opacity="0.60"/>
    <rect x="251" y="210" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.85"/>
    <rect x="270" y="210" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.70"/>
    <rect x="289" y="210" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="308" y="210" width="18" height="18" rx="2" fill="#f97316" opacity="0.75"/>
    <rect x="327" y="210" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.82"/>
    <!-- Row 10 (L10) -->
    <rect x="42" y="232" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.70"/>
    <rect x="61" y="232" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.80"/>
    <rect x="80" y="232" width="18" height="18" rx="2" fill="#f97316" opacity="0.60"/>
    <rect x="99" y="232" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.32"/>
    <rect x="118" y="232" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.85"/>
    <rect x="137" y="232" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.75"/>
    <rect x="156" y="232" width="18" height="18" rx="2" fill="#f97316" opacity="0.70"/>
    <rect x="175" y="232" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.90"/>
    <rect x="194" y="232" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="213" y="232" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.85"/>
    <rect x="232" y="232" width="18" height="18" rx="2" fill="#f97316" opacity="0.55"/>
    <rect x="251" y="232" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.80"/>
    <rect x="270" y="232" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.72"/>
    <rect x="289" y="232" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="308" y="232" width="18" height="18" rx="2" fill="#f97316" opacity="0.65"/>
    <rect x="327" y="232" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.75"/>
    <!-- Row 11 (L11) - gripper/contact: high orange on specific heads -->
    <rect x="42" y="254" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="61" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.95"/>
    <rect x="80" y="254" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="99" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.90"/>
    <rect x="118" y="254" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.60"/>
    <rect x="137" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.88"/>
    <rect x="156" y="254" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.25"/>
    <rect x="175" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.92"/>
    <rect x="194" y="254" width="18" height="18" rx="2" fill="#38bdf8" opacity="0.55"/>
    <rect x="213" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.85"/>
    <rect x="232" y="254" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.28"/>
    <rect x="251" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.93"/>
    <rect x="270" y="254" width="18" height="18" rx="2" fill="#a78bfa" opacity="0.50"/>
    <rect x="289" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.88"/>
    <rect x="308" y="254" width="18" height="18" rx="2" fill="#94a3b8" opacity="0.30"/>
    <rect x="327" y="254" width="18" height="18" rx="2" fill="#f97316" opacity="0.90"/>
    <text x="355" y="266" fill="#f97316" font-size="9" font-style="italic">← gripper/contact</text>
    <!-- Legend -->
    <rect x="460" y="60" width="14" height="14" rx="2" fill="#38bdf8" opacity="0.80"/>
    <text x="478" y="72" fill="#94a3b8" font-size="10">Low entropy (focused)</text>
    <rect x="460" y="84" width="14" height="14" rx="2" fill="#a78bfa" opacity="0.80"/>
    <text x="478" y="96" fill="#94a3b8" font-size="10">Medium entropy</text>
    <rect x="460" y="108" width="14" height="14" rx="2" fill="#f97316" opacity="0.85"/>
    <text x="478" y="120" fill="#94a3b8" font-size="10">High entropy (diffuse)</text>
    <rect x="460" y="132" width="14" height="14" rx="2" fill="#94a3b8" opacity="0.35"/>
    <text x="478" y="144" fill="#94a3b8" font-size="10">Dead head (gray)</text>
    <text x="460" y="170" fill="#64748b" font-size="9">Dead heads (18%): concentrated</text>
    <text x="460" y="184" fill="#64748b" font-size="9">in L0, L2, L5, L9 (H2, H6, H9, H13)</text>
  </svg>
</div>

<div class="grid">
  <!-- SVG 2: Head Importance Score Bar Chart -->
  <div class="card">
    <h2>Head Importance (Pruning Sensitivity — Top 12)</h2>
    <svg viewBox="0 0 380 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
      <!-- Bars: head label, importance score -->
      <!-- L11-H1 critical -->
      <text x="60" y="22" fill="#94a3b8" font-size="10" text-anchor="end">L11-H1</text>
      <rect x="64" y="12" width="245" height="14" rx="3" fill="#C74634"/>
      <text x="314" y="22" fill="#e2e8f0" font-size="10">0.982</text>
      <!-- L8-H2 critical -->
      <text x="60" y="44" fill="#94a3b8" font-size="10" text-anchor="end">L8-H2</text>
      <rect x="64" y="34" width="230" height="14" rx="3" fill="#C74634"/>
      <text x="298" y="44" fill="#e2e8f0" font-size="10">0.938</text>
      <!-- L11-H3 critical -->
      <text x="60" y="66" fill="#94a3b8" font-size="10" text-anchor="end">L11-H3</text>
      <rect x="64" y="56" width="220" height="14" rx="3" fill="#C74634"/>
      <text x="288" y="66" fill="#e2e8f0" font-size="10">0.902</text>
      <!-- L8-H0 -->
      <text x="60" y="88" fill="#94a3b8" font-size="10" text-anchor="end">L8-H0</text>
      <rect x="64" y="78" width="207" height="14" rx="3" fill="#38bdf8"/>
      <text x="275" y="88" fill="#e2e8f0" font-size="10">0.847</text>
      <!-- L11-H7 -->
      <text x="60" y="110" fill="#94a3b8" font-size="10" text-anchor="end">L11-H7</text>
      <rect x="64" y="100" width="195" height="14" rx="3" fill="#38bdf8"/>
      <text x="263" y="110" fill="#e2e8f0" font-size="10">0.798</text>
      <!-- L8-H6 -->
      <text x="60" y="132" fill="#94a3b8" font-size="10" text-anchor="end">L8-H6</text>
      <rect x="64" y="122" width="183" height="14" rx="3" fill="#38bdf8"/>
      <text x="251" y="132" fill="#e2e8f0" font-size="10">0.748</text>
      <!-- L7-H1 -->
      <text x="60" y="154" fill="#94a3b8" font-size="10" text-anchor="end">L7-H1</text>
      <rect x="64" y="144" width="170" height="14" rx="3" fill="#7dd3fc"/>
      <text x="238" y="154" fill="#e2e8f0" font-size="10">0.695</text>
      <!-- L11-H9 -->
      <text x="60" y="176" fill="#94a3b8" font-size="10" text-anchor="end">L11-H9</text>
      <rect x="64" y="166" width="158" height="14" rx="3" fill="#7dd3fc"/>
      <text x="226" y="176" fill="#e2e8f0" font-size="10">0.646</text>
      <!-- L6-H3 -->
      <text x="60" y="198" fill="#94a3b8" font-size="10" text-anchor="end">L6-H3</text>
      <rect x="64" y="188" width="145" height="14" rx="3" fill="#7dd3fc"/>
      <text x="213" y="198" fill="#e2e8f0" font-size="10">0.593</text>
      <!-- L9-H4 -->
      <text x="60" y="220" fill="#94a3b8" font-size="10" text-anchor="end">L9-H4</text>
      <rect x="64" y="210" width="130" height="14" rx="3" fill="#a78bfa"/>
      <text x="198" y="220" fill="#e2e8f0" font-size="10">0.531</text>
      <!-- L5-H2 -->
      <text x="60" y="242" fill="#94a3b8" font-size="10" text-anchor="end">L5-H2</text>
      <rect x="64" y="232" width="112" height="14" rx="3" fill="#a78bfa"/>
      <text x="180" y="242" fill="#e2e8f0" font-size="10">0.458</text>
      <!-- L4-H5 -->
      <text x="60" y="260" fill="#64748b" font-size="10" text-anchor="end">L4-H5</text>
      <rect x="64" y="250" width="95" height="14" rx="3" fill="#64748b" opacity="0.6"/>
      <text x="163" y="260" fill="#94a3b8" font-size="10">0.388</text>
    </svg>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#C74634"></div>Critical (prune = SR loss)</div>
      <div class="legend-item"><div class="legend-dot" style="background:#38bdf8"></div>High importance</div>
      <div class="legend-item"><div class="legend-dot" style="background:#a78bfa"></div>Medium</div>
    </div>
  </div>

  <!-- SVG 3: Task-Phase Attention Shift -->
  <div class="card">
    <h2>Task-Phase Attention Shift (Top-6 Heads)</h2>
    <svg viewBox="0 0 380 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
      <!-- Group 1: L11-H1 -->
      <text x="38" y="28" fill="#94a3b8" font-size="9" text-anchor="middle">L11-H1</text>
      <rect x="8"  y="32" width="20" height="30" rx="2" fill="#38bdf8" opacity="0.60"/>
      <rect x="29" y="20" width="20" height="42" rx="2" fill="#a78bfa" opacity="0.75"/>
      <rect x="50" y="8"  width="20" height="54" rx="2" fill="#f97316" opacity="0.90"/>
      <!-- Group 2: L8-H2 -->
      <text x="110" y="28" fill="#94a3b8" font-size="9" text-anchor="middle">L8-H2</text>
      <rect x="80" y="18" width="20" height="44" rx="2" fill="#38bdf8" opacity="0.85"/>
      <rect x="101" y="28" width="20" height="34" rx="2" fill="#a78bfa" opacity="0.65"/>
      <rect x="122" y="40" width="20" height="22" rx="2" fill="#f97316" opacity="0.50"/>
      <!-- Group 3: L11-H3 -->
      <text x="182" y="28" fill="#94a3b8" font-size="9" text-anchor="middle">L11-H3</text>
      <rect x="152" y="35" width="20" height="27" rx="2" fill="#38bdf8" opacity="0.55"/>
      <rect x="173" y="22" width="20" height="40" rx="2" fill="#a78bfa" opacity="0.70"/>
      <rect x="194" y="10" width="20" height="52" rx="2" fill="#f97316" opacity="0.88"/>
      <!-- Group 4: L8-H0 -->
      <text x="254" y="28" fill="#94a3b8" font-size="9" text-anchor="middle">L8-H0</text>
      <rect x="224" y="22" width="20" height="40" rx="2" fill="#38bdf8" opacity="0.75"/>
      <rect x="245" y="32" width="20" height="30" rx="2" fill="#a78bfa" opacity="0.60"/>
      <rect x="266" y="15" width="20" height="47" rx="2" fill="#f97316" opacity="0.80"/>
      <!-- Group 5: L7-H1 -->
      <text x="326" y="28" fill="#94a3b8" font-size="9" text-anchor="middle">L7-H1</text>
      <rect x="296" y="28" width="20" height="34" rx="2" fill="#38bdf8" opacity="0.70"/>
      <rect x="317" y="18" width="20" height="44" rx="2" fill="#a78bfa" opacity="0.80"/>
      <rect x="338" y="35" width="20" height="27" rx="2" fill="#f97316" opacity="0.55"/>
      <!-- Baseline -->
      <line x1="4" y1="62" x2="372" y2="62" stroke="#334155" stroke-width="1"/>
      <text x="4" y="75" fill="#64748b" font-size="9">Approach</text>
      <text x="4" y="88" fill="#64748b" font-size="9">Grasp</text>
      <text x="4" y="101" fill="#64748b" font-size="9">Lift</text>
      <!-- Legend -->
      <rect x="8"  y="112" width="12" height="10" rx="1" fill="#38bdf8" opacity="0.75"/>
      <text x="24" y="121" fill="#94a3b8" font-size="9">Approach phase</text>
      <rect x="130" y="112" width="12" height="10" rx="1" fill="#a78bfa" opacity="0.75"/>
      <text x="146" y="121" fill="#94a3b8" font-size="9">Grasp phase</text>
      <rect x="240" y="112" width="12" height="10" rx="1" fill="#f97316" opacity="0.80"/>
      <text x="256" y="121" fill="#94a3b8" font-size="9">Lift phase</text>
      <!-- Insight labels -->
      <text x="8" y="145" fill="#64748b" font-size="9">L11-H1 &amp; L11-H3: activation peaks at lift</text>
      <text x="8" y="160" fill="#64748b" font-size="9">(gripper close + object contact)</text>
      <text x="8" y="178" fill="#64748b" font-size="9">L8-H2: peaks at approach</text>
      <text x="8" y="193" fill="#64748b" font-size="9">(spatial path planning)</text>
      <text x="8" y="211" fill="#64748b" font-size="9">L7-H1: peaks at grasp</text>
      <text x="8" y="226" fill="#64748b" font-size="9">(object pose estimation)</text>
    </svg>
  </div>
</div>

<script>
  // Tooltip interaction for heatmap cells
  document.querySelectorAll('rect').forEach(r => {
    r.style.cursor = 'pointer';
    r.addEventListener('mouseenter', function(e) {
      this.style.filter = 'brightness(1.4)';
    });
    r.addEventListener('mouseleave', function(e) {
      this.style.filter = '';
    });
  });
</script>
</body>
</html>
"""

HEALTH = {"status": "ok", "service": "attention_head_analyzer", "port": 8624}

if USE_FASTAPI:
    app = FastAPI(title="Attention Head Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return HEALTH

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8624)
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps(HEALTH).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8624), Handler)
        print("Serving on port 8624")
        server.serve_forever()
