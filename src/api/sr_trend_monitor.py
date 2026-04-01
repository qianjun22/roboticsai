import datetime,fastapi,fastapi.responses,uvicorn
PORT=8108
SERVICE="sr_trend_monitor"
DESCRIPTION="Success Rate Trend Monitor - DAgger progress tracking"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
SR_HISTORY=[
    {"run":"BC_baseline","sr":0.05,"episodes":1000,"date":"2026-02-01"},
    {"run":"dagger_run5","sr":0.05,"episodes":150,"date":"2026-02-15"},
    {"run":"dagger_run6","sr":0.05,"episodes":120,"date":"2026-03-01"},
    {"run":"dagger_run7","sr":0.05,"episodes":120,"date":"2026-03-31","note":"server_restart_failed_iters2-4"},
    {"run":"dagger_run8","sr":None,"episodes":0,"date":"2026-04-01","status":"running_iter1_beta0.30","fix":"server_restart_cwd_port_fixed"},
]
TARGET_SR=0.65
@app.get("/history")
def history(): return SR_HISTORY
@app.get("/trend")
def trend(): return {"baseline":0.05,"latest":SR_HISTORY[-2]["sr"],"target":TARGET_SR,"runs_completed":len([r for r in SR_HISTORY if r["sr"] is not None])}

@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
