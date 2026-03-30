"""knowledge_distillation_trainer.py
OCI Robot Cloud — GR00T N1.6 Fine-Tuning Platform
Structured knowledge distillation: GR00T 3B teacher → edge student models.
Dependencies: stdlib + numpy only."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

TEACHER_MODEL="gr00t_n1.6_3b"; TEACHER_PARAMS_M=3000; TEACHER_VRAM_GB=6.7; TEACHER_SR=0.71
DISTILL_METHODS=["bc_only","kl_divergence","feature_matching","combined_bc_kl","progressive"]
OCI_COST_PER_STEP=0.000043
JETSON_DEVICES: Dict[str,Tuple[float,float]]={"Jetson AGX Orin":(64.0,275.0),"Jetson Orin NX 16GB":(16.0,100.0),"Jetson Orin NX 8GB":(8.0,70.0),"Jetson Nano":(4.0,21.0)}

@dataclass
class StudentArchitecture:
    arch_id:str; n_layers:int; hidden_dim:int; n_heads:int
    param_count_m:float; vram_gb_inference:float; target_device:str

@dataclass
class DistillationRun:
    run_id:str; teacher_model:str; student_arch:StudentArchitecture; distill_method:str
    n_demos:int; n_steps:int; final_mae:float; final_sr:float
    jetson_latency_ms:float; compression_ratio:float; cost_usd:float

STUDENT_ARCHITECTURES: List[StudentArchitecture] = [
    StudentArchitecture("student_xl",8,512,8,250.0,1.2,"Jetson AGX Orin"),
    StudentArchitecture("student_lg",6,384,6,120.0,0.6,"Jetson Orin NX 16GB"),
    StudentArchitecture("student_md",4,256,4,60.0,0.3,"Jetson Orin NX 8GB"),
    StudentArchitecture("student_sm",2,128,2,15.0,0.1,"Jetson Nano"),
]

_BC_BASE={"student_xl":0.88,"student_lg":0.82,"student_md":0.74,"student_sm":0.62}
_METHOD_BOOST={"bc_only":{a:0.00 for a in _BC_BASE},"kl_divergence":{"student_xl":0.048,"student_lg":0.052,"student_md":0.055,"student_sm":0.060},"feature_matching":{"student_xl":0.038,"student_lg":0.040,"student_md":0.043,"student_sm":0.050},"combined_bc_kl":{"student_xl":0.057,"student_lg":0.063,"student_md":0.068,"student_sm":0.074},"progressive":{"student_xl":0.054,"student_lg":0.060,"student_md":0.065,"student_sm":0.072}}
_METHOD_STEPS={"bc_only":5000,"kl_divergence":7000,"feature_matching":8000,"combined_bc_kl":10000,"progressive":12000}
_METHOD_DEMOS={"bc_only":1000,"kl_divergence":1000,"feature_matching":1000,"combined_bc_kl":1000,"progressive":1500}

def _simulate_sr(arch: StudentArchitecture, method: str, rng) -> float:
    sr_ratio=_BC_BASE[arch.arch_id]+_METHOD_BOOST[method][arch.arch_id]
    return float(np.clip(TEACHER_SR*(sr_ratio+rng.normal(0.0,0.005)),0.05,0.99))

def _simulate_mae(sr: float) -> float: return round(0.025+0.22*(1.0-sr),4)

def _jetson_latency(arch: StudentArchitecture, device_name: str) -> float:
    _,tflops=JETSON_DEVICES[device_name]
    return round((arch.param_count_m/TEACHER_PARAMS_M)*(275.0/tflops)*226.0,1)

def run_distillation_suite(seed: int = 42) -> List[DistillationRun]:
    rng=np.random.default_rng(seed); runs=[]
    for arch in STUDENT_ARCHITECTURES:
        for method in DISTILL_METHODS:
            sr=_simulate_sr(arch,method,rng)
            runs.append(DistillationRun(
                run_id=f"{arch.arch_id}__{method}",teacher_model=TEACHER_MODEL,student_arch=arch,distill_method=method,
                n_demos=_METHOD_DEMOS[method],n_steps=_METHOD_STEPS[method],
                final_mae=_simulate_mae(sr),final_sr=sr,
                jetson_latency_ms=_jetson_latency(arch,arch.target_device),
                compression_ratio=round(TEACHER_PARAMS_M/arch.param_count_m,1),
                cost_usd=round(_METHOD_STEPS[method]*OCI_COST_PER_STEP,4)))
    return runs

def find_recommended_config(runs: List[DistillationRun], jetson_vram_gb: float = 16.0) -> DistillationRun:
    eligible=[r for r in runs if r.student_arch.vram_gb_inference<=jetson_vram_gb]
    if not eligible: raise ValueError(f"No student fits {jetson_vram_gb} GB")
    return max(eligible,key=lambda r:r.final_sr)

def _sr_pct(sr): return f"{sr*100:.1f}%"
def _cell_color(sr,col_max):
    r=sr/col_max if col_max>0 else 0
    return "#d1fae5" if r>=0.98 else ("#fef9c3" if r>=0.93 else "#ffffff")

def _svg_cost_sr(runs: List[DistillationRun]) -> str:
    W,H=520,280; PAD_L,PAD_R,PAD_T,PAD_B=60,120,20,50
    costs=[r.cost_usd for r in runs]; srs=[r.final_sr for r in runs]
    x_min,x_max=0.0,max(costs)*1.12; y_min,y_max=min(srs)*0.95,1.0
    arch_colors={"student_xl":"#6366f1","student_lg":"#10b981","student_md":"#f59e0b","student_sm":"#ef4444"}
    def tx(v): return PAD_L+(v-x_min)/(x_max-x_min)*(W-PAD_L-PAD_R)
    def ty(v): return H-PAD_B-(v-y_min)/(y_max-y_min)*(H-PAD_T-PAD_B)
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="font-family:monospace;font-size:10px;background:#f9fafb;border-radius:8px;">',
           f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}" stroke="#6b7280" stroke-width="1"/>',
           f'<line x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-PAD_R}" y2="{H-PAD_B}" stroke="#6b7280" stroke-width="1"/>',
           f'<text x="{PAD_L+(W-PAD_L-PAD_R)//2}" y="{H-6}" text-anchor="middle" fill="#374151" font-size="11">Training Cost (USD)</text>',
           f'<text x="12" y="{H//2}" text-anchor="middle" fill="#374151" font-size="11" transform="rotate(-90,12,{H//2})">Success Rate</text>']
    for sr_tick in [0.4,0.5,0.6,0.7]:
        if sr_tick<y_min or sr_tick>y_max: continue
        yp=ty(sr_tick)
        lines.append(f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{W-PAD_R}" y2="{yp:.1f}" stroke="#e5e7eb" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{PAD_L-4}" y="{yp+4:.1f}" text-anchor="end" fill="#6b7280">{sr_tick:.1f}</text>')
    for r in runs:
        cx=tx(r.cost_usd); cy=ty(r.final_sr); col=arch_colors.get(r.student_arch.arch_id,"#999")
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{col}" fill-opacity="0.82" stroke="white" stroke-width="1"><title>{r.run_id} SR={_sr_pct(r.final_sr)} cost=${r.cost_usd:.4f}</title></circle>')
    legend_x=W-PAD_R+8
    for i,(arch_id,col) in enumerate(arch_colors.items()):
        ly=PAD_T+i*22
        lines.append(f'<circle cx="{legend_x+6}" cy="{ly+6}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{legend_x+16}" y="{ly+10}" fill="#374151" font-size="10">{arch_id}</text>')
    lines.append("</svg>")
    return "\n".join(lines)

def _jetson_compat_table(runs: List[DistillationRun]) -> str:
    devices=list(JETSON_DEVICES.keys())
    rows=[]
    for arch in STUDENT_ARCHITECTURES:
        cells=[f"<td><strong>{arch.arch_id}</strong></td>"]
        for device in devices:
            vram,_=JETSON_DEVICES[device]
            if arch.vram_gb_inference>vram: cells.append('<td style="color:#ef4444;background:#fee2e2;">N/A</td>')
            else:
                lat=_jetson_latency(arch,device); bg="#d1fae5" if device==arch.target_device else ""
                cells.append(f"<td{' style=\"background:'+bg+';\"' if bg else ''}>{lat} ms</td>")
        rows.append("<tr>"+"".join(cells)+"</tr>")
    header="<tr><th>Arch</th>"+"".join(f"<th>{d}</th>" for d in devices)+"</tr>"
    return "<table><thead>"+header+"</thead><tbody>"+"".join(rows)+"</tbody></table>"

def generate_distillation_report(runs: List[DistillationRun]) -> str:
    arch_ids=[a.arch_id for a in STUDENT_ARCHITECTURES]
    matrix={a.arch_id:{} for a in STUDENT_ARCHITECTURES}
    for r in runs: matrix[r.student_arch.arch_id][r.distill_method]=r
    method_max_sr={m:max(matrix[a][m].final_sr for a in arch_ids if m in matrix[a]) for m in DISTILL_METHODS}
    header_cells="<th>Architecture</th>"+"".join(f"<th>{m.replace('_',' ')}</th>" for m in DISTILL_METHODS)
    table_rows=[]
    for arch in STUDENT_ARCHITECTURES:
        cells=[f"<td><code>{arch.arch_id}</code><br><span style='font-size:11px;color:#6b7280'>{arch.param_count_m:.0f}M params</span></td>"]
        for m in DISTILL_METHODS:
            run=matrix[arch.arch_id].get(m)
            if run is None: cells.append("<td>—</td>"); continue
            bg=_cell_color(run.final_sr,method_max_sr[m])
            best_m=max(DISTILL_METHODS,key=lambda mm:matrix[arch.arch_id].get(mm,run).final_sr)
            wt="font-weight:bold;" if m==best_m else ""
            cells.append(f'<td style="background:{bg};{wt}">{_sr_pct(run.final_sr)}</td>')
        table_rows.append("<tr>"+"".join(cells)+"</tr>")
    rec=find_recommended_config(runs,16.0)
    compat=_jetson_compat_table(runs); svg=_svg_cost_sr(runs)
    html=f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>OCI Robot Cloud — Knowledge Distillation</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:24px;background:#f3f4f6;color:#111827}}
h1{{font-size:22px;margin-bottom:4px;color:#1e3a5f}}.subtitle{{color:#6b7280;font-size:13px;margin-bottom:24px}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:8px}}
th{{background:#1e3a5f;color:white;text-align:left;padding:10px 12px;font-size:12px;font-weight:600}}
td{{padding:9px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;text-align:center}}
td:first-child{{text-align:left}}tr:last-child td{{border-bottom:none}}
.section{{margin-bottom:32px}}.section-title{{font-size:15px;font-weight:600;color:#374151;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid #e5e7eb}}
.recommend{{background:#eff6ff;border:1px solid #93c5fd;border-radius:10px;padding:18px 22px;margin-top:24px}}
.recommend h3{{margin:0 0 8px;color:#1e40af;font-size:15px}}
.recommend p{{margin:0;color:#1e3a8a;font-size:13px;line-height:1.7}}
.meta-row{{display:flex;gap:24px;margin-bottom:6px;font-size:12px;color:#6b7280;flex-wrap:wrap}}
.meta-row span{{background:#e5e7eb;border-radius:4px;padding:2px 8px}}</style></head>
<body>
<h1>OCI Robot Cloud — Knowledge Distillation Trainer</h1>
<div class="subtitle">Teacher: <strong>{TEACHER_MODEL}</strong> ({TEACHER_PARAMS_M:,}M params, {TEACHER_VRAM_GB}GB VRAM) &bull; SR: <strong>{TEACHER_SR:.0%}</strong> (DAgger run9 v2.2)</div>
<div class="meta-row"><span>{len(STUDENT_ARCHITECTURES)} student archs</span><span>{len(DISTILL_METHODS)} methods</span><span>{len(runs)} total runs</span><span>OCI A100 &bull; ${OCI_COST_PER_STEP:.6f}/step</span></div>
<div class="section" style="margin-top:24px"><div class="section-title">SR Matrix — green = column best</div>
<table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
<div class="section"><div class="section-title">Jetson Compatibility Matrix</div>{compat}</div>
<div class="section"><div class="section-title">Cost vs SR Scatter</div>{svg}</div>
<div class="recommend"><h3>Recommended: {rec.run_id}</h3>
<p>Arch: <strong>{rec.student_arch.arch_id}</strong> ({rec.student_arch.param_count_m:.0f}M, {rec.student_arch.vram_gb_inference}GB) &bull; Compression: <strong>{rec.compression_ratio:.0f}×</strong> &bull; Method: <strong>{rec.distill_method.replace('_',' ')}</strong><br>
SR: <strong>{_sr_pct(rec.final_sr)}</strong> &bull; MAE: <strong>{rec.final_mae:.4f}</strong> &bull; Latency: <strong>{rec.jetson_latency_ms}ms</strong> &bull; Cost: <strong>${rec.cost_usd:.4f}</strong></p></div>
</body></html>"""
    out_path="/tmp/knowledge_distillation_trainer.html"
    with open(out_path,"w",encoding="utf-8") as fh: fh.write(html)
    print(f"[distillation] Report saved → {out_path}")
    return html

def main() -> None:
    print("="*72+"\nOCI Robot Cloud — Knowledge Distillation Trainer\n"+"="*72)
    print(f"Teacher: {TEACHER_MODEL}  SR={TEACHER_SR:.0%}  params={TEACHER_PARAMS_M:,}M  VRAM={TEACHER_VRAM_GB}GB\n")
    runs=run_distillation_suite(seed=42)
    run_map={a.arch_id:{} for a in STUDENT_ARCHITECTURES}
    for r in runs: run_map[r.student_arch.arch_id][r.distill_method]=r
    col_w=14
    hdr=f"{'Architecture':<16}"+"".join(f"{m[:col_w]:>{col_w}}" for m in DISTILL_METHODS)
    print(hdr+"\n"+"-"*len(hdr))
    for arch in STUDENT_ARCHITECTURES:
        row=f"{arch.arch_id:<16}"
        for m in DISTILL_METHODS:
            r=run_map[arch.arch_id].get(m)
            row+=f"{(_sr_pct(r.final_sr) if r else '—'):>{col_w}}"
        print(row)
    rec=find_recommended_config(runs,16.0)
    print(f"\nRecommended (<=16GB): {rec.run_id}  SR={_sr_pct(rec.final_sr)}  MAE={rec.final_mae:.4f}  latency={rec.jetson_latency_ms}ms  cost=${rec.cost_usd:.4f}  {rec.compression_ratio:.0f}x")
    generate_distillation_report(runs)

if __name__ == "__main__": main()
