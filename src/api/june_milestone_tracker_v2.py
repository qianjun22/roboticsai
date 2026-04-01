import datetime,fastapi,uvicorn
PORT=8295
SERVICE="june_milestone_tracker_v2"
DESCRIPTION="June 2026 milestones v2 — NVIDIA meeting + design partner live"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/milestones')
def m(): return {'nvidia_meeting':'2026-06-15','design_partner_pilot_live':'2026-06-01','dagger_run11_start':'2026-06-01','target_sr_by_july':'40%','mrr_target':3000,'headcount':1}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
