"""customer_trial_manager.py
Manages 30-day free trial lifecycle for OCI Robot Cloud design-partner prospects.
OCI Robot Cloud | Oracle Confidential | Port 8085"""
from __future__ import annotations
import json, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

PORT = 8085
TRIAL_GPU_HOURS = 10.0
TRIAL_DAYS = 30
TRIAL_TIERS = ["pilot","growth","enterprise"]
STATUS_VALUES = ["pending","active","completed","converted","churned"]
_UTC = timezone.utc

@dataclass
class TrialAccount:
    trial_id: str; company: str; contact_email: str; robot_type: str; use_case: str
    tier_requested: str; status: str; start_date: Optional[str]; end_date: Optional[str]
    gpu_hours_used: float; gpu_hours_limit: float; jobs_run: int; sr_achieved: float; notes: str = ""

@dataclass
class TrialEvent:
    event_id: str; trial_id: str; event_type: str; timestamp: str; details: str = ""

_TRIALS: List[TrialAccount] = [
    TrialAccount("trial_001","Wandelbots GmbH","pilot@wandelbots.com","welding_robot","Arc welding path planning with GR00T N1.6","growth","active","2026-03-05","2026-04-04",7.2,TRIAL_GPU_HOURS,3,0.58,"Strong engagement; requested custom SDG pipeline demo"),
    TrialAccount("trial_002","Machina Labs","ai@machinalabs.com","metal_forming","Force-controlled sheet metal deformation","enterprise","converted","2026-02-01","2026-03-03",9.8,TRIAL_GPU_HOURS,8,0.71,"Converted to enterprise contract; $120k ACV signed"),
    TrialAccount("trial_003","Robust AI","eng@robustai.com","warehouse_pick","Mixed-SKU bin picking in dynamic environments","growth","active","2026-03-15","2026-04-14",2.1,TRIAL_GPU_HOURS,1,0.05,"AT-RISK: low engagement, SR at baseline; needs onboarding call"),
    TrialAccount("trial_004","Formant Inc","product@formant.io","inspection_robot","Visual anomaly detection during facility patrol","pilot","active","2026-03-10","2026-04-09",4.5,TRIAL_GPU_HOURS,2,0.41,"Moderate progress; SR improving across jobs"),
    TrialAccount("trial_005","Matic Robots","dev@maticrobots.com","floor_cleaning","Autonomous floor-cleaning for residential spaces","pilot","churned","2026-02-20","2026-03-21",0.3,TRIAL_GPU_HOURS,0,0.00,"Never completed onboarding; tech lead left company"),
]

_EVENTS: List[TrialEvent] = [
    TrialEvent("evt_001","trial_001","created","2026-03-04T18:00:00Z","Trial signup via OCI marketplace"),
    TrialEvent("evt_002","trial_001","activated","2026-03-05T09:00:00Z","Account activated"),
    TrialEvent("evt_003","trial_001","job_run","2026-03-10T14:30:00Z","Fine-tune job #1 (500 steps)"),
    TrialEvent("evt_004","trial_002","created","2026-01-31T10:00:00Z","Trial signup via sales"),
    TrialEvent("evt_005","trial_002","activated","2026-02-01T09:00:00Z","Account activated"),
    TrialEvent("evt_006","trial_002","converted","2026-03-04T17:00:00Z","Converted to enterprise; contract signed"),
    TrialEvent("evt_007","trial_003","created","2026-03-14T11:00:00Z","Trial signup via partner referral"),
    TrialEvent("evt_008","trial_003","activated","2026-03-15T09:00:00Z","Account activated"),
    TrialEvent("evt_009","trial_004","created","2026-03-09T15:00:00Z","Trial signup via OCI marketplace"),
    TrialEvent("evt_010","trial_004","activated","2026-03-10T09:00:00Z","Account activated"),
    TrialEvent("evt_011","trial_005","created","2026-02-19T12:00:00Z","Trial signup via website"),
    TrialEvent("evt_012","trial_005","activated","2026-02-20T09:00:00Z","Account activated"),
    TrialEvent("evt_013","trial_005","churned","2026-03-22T09:00:00Z","Trial expired with no engagement"),
]

def _now_iso(): return datetime.now(_UTC).isoformat()
def _is_at_risk(t: TrialAccount) -> bool:
    if t.status != "active" or t.start_date is None: return False
    elapsed = (datetime.now(_UTC) - datetime.fromisoformat(t.start_date).replace(tzinfo=_UTC)).days
    return elapsed > 15 and t.sr_achieved < 0.30
def _days_remaining(t: TrialAccount) -> Optional[int]:
    if t.end_date is None: return None
    return max(0,(datetime.fromisoformat(t.end_date).replace(tzinfo=_UTC)-datetime.now(_UTC)).days)

def get_all_trials() -> List[dict]:
    return [{**asdict(t),"at_risk":_is_at_risk(t),"days_remaining":_days_remaining(t)} for t in _TRIALS]

def get_trial(trial_id: str) -> Optional[dict]:
    for t in _TRIALS:
        if t.trial_id == trial_id:
            return {**asdict(t),"at_risk":_is_at_risk(t),"days_remaining":_days_remaining(t),
                    "events":[asdict(e) for e in _EVENTS if e.trial_id==trial_id]}
    return None

def create_trial(company,contact_email,robot_type,use_case,tier_requested,notes="") -> dict:
    tid = f"trial_{str(uuid.uuid4())[:8]}"
    t = TrialAccount(tid,company,contact_email,robot_type,use_case,
        tier_requested if tier_requested in TRIAL_TIERS else "pilot",
        "pending",None,None,0.0,TRIAL_GPU_HOURS,0,0.0,notes)
    _TRIALS.append(t)
    _EVENTS.append(TrialEvent(f"evt_{str(uuid.uuid4())[:8]}",tid,"created",_now_iso(),f"Trial created for {company}"))
    return asdict(t)

def activate_trial(trial_id: str) -> Optional[dict]:
    for t in _TRIALS:
        if t.trial_id == trial_id:
            if t.status != "pending": return {"error":f"Cannot activate '{t.status}'"}
            now = datetime.now(_UTC)
            t.status="active"; t.start_date=now.date().isoformat(); t.end_date=(now+timedelta(days=TRIAL_DAYS)).date().isoformat()
            _EVENTS.append(TrialEvent(f"evt_{str(uuid.uuid4())[:8]}",trial_id,"activated",_now_iso(),f"Trial activated; ends {t.end_date}"))
            return asdict(t)
    return None

def convert_trial(trial_id: str) -> Optional[dict]:
    for t in _TRIALS:
        if t.trial_id == trial_id:
            if t.status not in ("active","completed"): return {"error":f"Cannot convert '{t.status}'"}
            t.status="converted"
            _EVENTS.append(TrialEvent(f"evt_{str(uuid.uuid4())[:8]}",trial_id,"converted",_now_iso(),"Trial converted to paying customer"))
            return asdict(t)
    return None

def get_usage(trial_id: str) -> Optional[dict]:
    for t in _TRIALS:
        if t.trial_id == trial_id:
            return {"trial_id":trial_id,"company":t.company,"gpu_hours_used":t.gpu_hours_used,
                    "gpu_hours_limit":t.gpu_hours_limit,"gpu_hours_remaining":round(t.gpu_hours_limit-t.gpu_hours_used,2),
                    "utilization_pct":round(t.gpu_hours_used/t.gpu_hours_limit*100,1),"jobs_run":t.jobs_run,"sr_achieved":t.sr_achieved}
    return None

def get_summary() -> dict:
    total=len(_TRIALS); converted=sum(1 for t in _TRIALS if t.status=="converted")
    active=sum(1 for t in _TRIALS if t.status=="active"); churned=sum(1 for t in _TRIALS if t.status=="churned")
    at_risk=sum(1 for t in _TRIALS if _is_at_risk(t))
    completed_or_conv=[t for t in _TRIALS if t.status in ("converted","completed","churned")]
    conv_rate=converted/len(completed_or_conv) if completed_or_conv else 0.0
    active_trials=[t for t in _TRIALS if t.status in ("active","converted","completed")]
    avg_sr=sum(t.sr_achieved for t in active_trials)/len(active_trials) if active_trials else 0.0
    avg_gpu=sum(t.gpu_hours_used for t in _TRIALS)/total if total else 0.0
    return {"total_trials":total,"active":active,"converted":converted,"churned":churned,
            "at_risk":at_risk,"conversion_rate":round(conv_rate,3),"avg_sr_active":round(avg_sr,3),"avg_gpu_hours_consumed":round(avg_gpu,2)}

_STATUS_ORDER=["pending","active","completed","converted","churned"]
_STATUS_COLOR={"pending":("#64748b","#f1f5f9"),"active":("#2563eb","#dbeafe"),"completed":("#16a34a","#dcfce7"),"converted":("#7c3aed","#ede9fe"),"churned":("#dc2626","#fee2e2")}

def _trial_card(t: TrialAccount) -> str:
    at_risk=_is_at_risk(t); bg="#fffbeb" if at_risk else "white"; border="1.5px solid #f59e0b" if at_risk else "1px solid #e2e8f0"
    risk_badge='<span class="badge risk">AT-RISK</span>' if at_risk else ""
    sr_color="#16a34a" if t.sr_achieved>=0.50 else ("#ca8a04" if t.sr_achieved>=0.20 else "#dc2626")
    days_str=f"{_days_remaining(t)}d left" if _days_remaining(t) is not None else "N/A"
    return (f"<div class='card' style='background:{bg};border:{border}'>"
            f"<div class='card-header'><span class='company'>{t.company}</span>{risk_badge}</div>"
            f"<div class='card-meta'>{t.robot_type} &nbsp;|&nbsp; {t.tier_requested}</div>"
            f"<div class='card-email'>{t.contact_email}</div>"
            f"<div class='card-stats'><span style='color:{sr_color};font-weight:700'>SR {t.sr_achieved:.0%}</span>"
            f" &nbsp;|&nbsp; {t.gpu_hours_used:.1f}/{t.gpu_hours_limit:.0f}h &nbsp;|&nbsp; {t.jobs_run} jobs &nbsp;|&nbsp; {days_str}</div>"
            f"<div class='card-notes'>{t.notes}</div></div>")

def generate_dashboard() -> str:
    summary=get_summary()
    columns_html=""
    for status in _STATUS_ORDER:
        fg,bg=_STATUS_COLOR[status]
        trials_in_col=[t for t in _TRIALS if t.status==status]
        cards="".join(_trial_card(t) for t in trials_in_col) or '<div style="color:#94a3b8;font-size:.82rem;padding:12px">No trials</div>'
        columns_html+=f"<div class='column'><div class='col-header' style='background:{bg};color:{fg}'>{status.upper()} <span class='col-count'>{len(trials_in_col)}</span></div>{cards}</div>"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Trial Manager</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;background:#f8fafc;color:#1e293b}}
header{{background:#0f172a;color:white;padding:20px 36px;display:flex;align-items:center;gap:18px}}
header .logo{{background:#C74634;color:white;font-weight:800;font-size:.9rem;padding:6px 12px;border-radius:6px}}
header h1{{font-size:1.4rem;font-weight:700}}header p{{color:#94a3b8;font-size:.82rem;margin-top:2px}}
.summary{{display:flex;gap:14px;padding:20px 36px;flex-wrap:wrap}}
.stat{{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:14px 22px;flex:1;min-width:130px}}
.stat-label{{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#64748b;font-weight:600}}
.stat-value{{font-size:1.7rem;font-weight:800;margin-top:4px}}
.kanban{{display:flex;gap:16px;padding:0 36px 40px;overflow-x:auto}}
.column{{flex:1;min-width:200px}}
.col-header{{font-size:.78rem;font-weight:700;letter-spacing:.07em;padding:8px 14px;border-radius:8px 8px 0 0;display:flex;justify-content:space-between}}
.col-count{{background:rgba(0,0,0,.12);border-radius:9px;padding:1px 7px;font-weight:700}}
.card{{background:white;border:1px solid #e2e8f0;border-radius:0 0 8px 8px;margin-bottom:10px;padding:14px}}
.card:not(:first-of-type){{border-radius:8px}}
.card-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:6px}}
.company{{font-weight:700;font-size:.9rem}}
.badge{{font-size:.65rem;font-weight:700;padding:2px 7px;border-radius:9px;white-space:nowrap}}
.badge.risk{{background:#fef3c7;color:#92400e;border:1px solid #fbbf24}}
.card-meta{{font-size:.75rem;color:#64748b;margin-top:4px}}
.card-email{{font-size:.72rem;color:#94a3b8;margin-top:2px}}
.card-stats{{font-size:.78rem;margin-top:8px;color:#475569}}
.card-notes{{font-size:.72rem;color:#94a3b8;margin-top:6px;font-style:italic;line-height:1.4}}
footer{{text-align:center;font-size:.75rem;color:#9ca3af;padding:20px;border-top:1px solid #e2e8f0}}</style></head>
<body>
<header><div><div class="logo">ORACLE</div></div><div><h1>OCI Robot Cloud — Customer Trial Manager</h1>
<p>Design Partner Pipeline &nbsp;|&nbsp; Port {PORT} &nbsp;|&nbsp; {TRIAL_DAYS}-day trials &nbsp;|&nbsp; {TRIAL_GPU_HOURS}h GPU</p></div></header>
<div class="summary">
<div class="stat"><div class="stat-label">Total</div><div class="stat-value">{summary['total_trials']}</div></div>
<div class="stat"><div class="stat-label">Active</div><div class="stat-value" style="color:#2563eb">{summary['active']}</div></div>
<div class="stat"><div class="stat-label">Converted</div><div class="stat-value" style="color:#7c3aed">{summary['converted']}</div></div>
<div class="stat"><div class="stat-label">At-Risk</div><div class="stat-value" style="color:#f59e0b">{summary['at_risk']}</div></div>
<div class="stat"><div class="stat-label">Conv Rate</div><div class="stat-value" style="color:#16a34a">{summary['conversion_rate']:.0%}</div></div>
<div class="stat"><div class="stat-label">Avg SR</div><div class="stat-value">{summary['avg_sr_active']:.0%}</div></div>
<div class="stat"><div class="stat-label">Avg GPU h</div><div class="stat-value">{summary['avg_gpu_hours_consumed']:.1f}h</div></div>
</div>
<div class="kanban">{columns_html}</div>
<footer>Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Design Partner Program</footer>
</body></html>"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    app = FastAPI(title="OCI Robot Cloud — Customer Trial Manager",version="1.0.0")
    class TrialCreateRequest(BaseModel):
        company:str; contact_email:str; robot_type:str; use_case:str; tier_requested:str; notes:str=""
    @app.get("/",response_class=HTMLResponse)
    async def dashboard(): return HTMLResponse(content=generate_dashboard())
    @app.get("/trials")
    async def list_trials(): return JSONResponse(content=get_all_trials())
    @app.get("/trials/{trial_id}")
    async def trial_detail(trial_id:str):
        r=get_trial(trial_id)
        if r is None: raise HTTPException(404,f"Trial {trial_id} not found")
        return JSONResponse(content=r)
    @app.post("/trials",status_code=201)
    async def create_new_trial(req:TrialCreateRequest):
        return JSONResponse(content=create_trial(req.company,req.contact_email,req.robot_type,req.use_case,req.tier_requested,req.notes),status_code=201)
    @app.post("/trials/{trial_id}/activate")
    async def activate(trial_id:str):
        r=activate_trial(trial_id)
        if r is None: raise HTTPException(404,f"Trial {trial_id} not found")
        if "error" in r: raise HTTPException(400,r["error"])
        return JSONResponse(content=r)
    @app.post("/trials/{trial_id}/convert")
    async def convert(trial_id:str):
        r=convert_trial(trial_id)
        if r is None: raise HTTPException(404,f"Trial {trial_id} not found")
        if "error" in r: raise HTTPException(400,r["error"])
        return JSONResponse(content=r)
    @app.get("/trials/{trial_id}/usage")
    async def usage(trial_id:str):
        r=get_usage(trial_id)
        if r is None: raise HTTPException(404,f"Trial {trial_id} not found")
        return JSONResponse(content=r)
    @app.get("/summary")
    async def summary_endpoint(): return JSONResponse(content=get_summary())
    _FASTAPI_AVAILABLE=True
except ImportError:
    _FASTAPI_AVAILABLE=False; app=None

def main() -> None:
    hdr=f"{'Trial ID':<14} {'Company':<20} {'Robot Type':<18} {'Status':<12} {'SR':>6} {'GPU h':>7} {'Jobs':>5} {'At-Risk'}"
    print("\n"+"="*len(hdr)+"\n  OCI Robot Cloud — Customer Trial Pipeline\n"+"="*len(hdr)+"\n"+hdr+"\n"+"-"*len(hdr))
    for t in _TRIALS:
        print(f"{t.trial_id:<14} {t.company:<20} {t.robot_type:<18} {t.status:<12} {t.sr_achieved:>6.0%} {t.gpu_hours_used:>6.1f}h {t.jobs_run:>5}   {'[!]' if _is_at_risk(t) else '   '}")
    s=get_summary()
    print("-"*len(hdr)+f"\n  {s['total_trials']} trials | {s['active']} active | {s['converted']} converted | Conv: {s['conversion_rate']:.0%} | Avg SR: {s['avg_sr_active']:.0%}\n"+"="*len(hdr))
    if _FASTAPI_AVAILABLE and app is not None:
        import uvicorn; uvicorn.run(app,host="0.0.0.0",port=PORT,log_level="info")

if __name__ == "__main__": main()
