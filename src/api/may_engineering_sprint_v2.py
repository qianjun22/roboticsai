import datetime,fastapi,uvicorn
PORT=8861
SERVICE="may_engineering_sprint_v2"
DESCRIPTION="May 2026 engineering sprint v2 — post 100pct SR, focus on hardening + sim-to-real"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/sprint")
def sprint(): return {"month":"May 2026","theme":"Robustness + Real-World Readiness","items":[{"task":"Run9 multi-iter DAgger (correct beta_decay)","owner":"jun","status":"in_progress"},{"task":"Multi-seed eval framework (5 seeds)","owner":"jun","status":"planned"},{"task":"gRPC inference API v2","owner":"jun","status":"planned"},{"task":"Real Franka procurement","owner":"oracle_IT","status":"pending_approval"},{"task":"CoRL paper v2 draft","owner":"jun","status":"in_progress"},{"task":"Design partner #1 signed","owner":"jun","status":"outreach"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
