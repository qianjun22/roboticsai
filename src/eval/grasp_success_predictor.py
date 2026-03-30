"""Grasp Success Predictor — FastAPI port 8378"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8378

def build_html():
    random.seed(19)
    
    # ROC curve (AUC = 0.91)
    # Approximate points along the curve
    roc_fpr = [0, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35, 0.50, 0.70, 1.0]
    roc_tpr = [0, 0.38, 0.62, 0.75, 0.83, 0.89, 0.93, 0.96, 0.98, 0.99, 1.0]
    
    roc_pts = " ".join(f"{30+fpr*240},{200-tpr*180}" for fpr, tpr in zip(roc_fpr, roc_tpr))
    diag_pts = "30,200 270,20"
    
    # Feature importance
    features = [
        ("wrist_rgb", 0.43, "#22c55e"),
        ("force_contact", 0.31, "#38bdf8"),
        ("ee_velocity", 0.19, "#f59e0b"),
        ("gripper_state", 0.12, "#a78bfa"),
        ("cube_pose", 0.09, "#C74634"),
        ("joint_torque", 0.07, "#64748b"),
    ]
    
    feat_bars = ""
    for i, (name, imp, color) in enumerate(features):
        y = 20 + i * 28
        w = int(imp * 400)
        feat_bars += f'<text x="105" y="{y+14}" text-anchor="end" fill="#94a3b8" font-size="9">{name}</text>'
        feat_bars += f'<rect x="110" y="{y}" width="{w}" height="20" fill="{color}" opacity="0.8" rx="2"/>'
        feat_bars += f'<text x="{115+w}" y="{y+14}" fill="{color}" font-size="9">{imp:.2f}</text>'

    # Early prediction accuracy at different frames
    frames = [4, 8, 12, 16, 20, 24, 32]
    # "% of episodes" at which prediction is possible, and accuracy
    early_acc = [0.61, 0.74, 0.82, 0.88, 0.91, 0.93, 0.95]
    compute_saved = [62, 51, 43, 34, 26, 18, 8]
    
    pts_acc = " ".join(f"{30+i*56},{180-early_acc[i]*160}" for i in range(len(frames)))
    pts_cs = " ".join(f"{30+i*56},{180-compute_saved[i]*1.6}" for i in range(len(frames)))

    return f"""<!DOCTYPE html><html><head><title>Grasp Success Predictor — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Grasp Success Predictor</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.91</div><div style="font-size:0.75em;color:#94a3b8">AUC-ROC</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">frame 16</div><div style="font-size:0.75em;color:#94a3b8">Optimal Cutoff</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">34%</div><div style="font-size:0.75em;color:#94a3b8">Compute Saved</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">wrist_rgb</div><div style="font-size:0.75em;color:#94a3b8">Top Feature</div></div>
</div>
<div class="grid">
<div class="card"><h2>ROC Curve (AUC = 0.91)</h2>
<svg viewBox="0 0 320 230"><rect width="320" height="230" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="205" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="205" x2="280" y2="205" stroke="#334155" stroke-width="1"/>
<polyline points="{diag_pts}" fill="none" stroke="#334155" stroke-dasharray="4,3" stroke-width="1"/>
<polyline points="{roc_pts}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
<!-- Area fill approximate -->
<polygon points="30,200 {roc_pts} 270,200" fill="#22c55e" fill-opacity="0.1"/>
<text x="100" y="100" fill="#22c55e" font-size="12" font-weight="bold">AUC = 0.91</text>
<text x="32" y="220" fill="#64748b" font-size="8">FPR</text>
<text x="5" y="100" fill="#64748b" font-size="8" transform="rotate(-90,5,100)">TPR</text>
</svg></div>
<div class="card"><h2>Feature Importance</h2>
<svg viewBox="0 0 420 185"><rect width="420" height="185" fill="#0f172a" rx="4"/>
{feat_bars}
</svg></div>
</div>
<div class="card" style="margin-top:16px"><h2>Early Prediction: Accuracy vs Compute Saved</h2>
<svg viewBox="0 0 440 210"><rect width="440" height="210" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="185" x2="430" y2="185" stroke="#334155" stroke-width="1"/>
<polyline points="{pts_acc}" fill="none" stroke="#22c55e" stroke-width="2"/>
<polyline points="{pts_cs}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,3"/>
<!-- Highlight frame 16 optimal -->
<circle cx="{30+3*56}" cy="{180-0.88*160}" r="6" fill="#22c55e" stroke="#fff" stroke-width="1.5"/>
<text x="{34+3*56}" y="{175-0.88*160}" fill="#22c55e" font-size="9">frame 16 ★</text>
{''.join(f'<text x="{30+i*56}" y="200" text-anchor="middle" fill="#64748b" font-size="8">f{frames[i]}</text>' for i in range(len(frames)))}
<text x="380" y="60" fill="#22c55e" font-size="8">Accuracy</text>
<text x="380" y="75" fill="#38bdf8" font-size="8">Compute saved%</text>
</svg></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Grasp Success Predictor")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"auc_roc":0.91,"compute_savings_pct":34}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()
