import datetime,fastapi,uvicorn
PORT=8354
SERVICE="sprint_tracker"
DESCRIPTION="Sprint tracker — 2-week engineering cycles"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/current')
def c(): return {'sprint':12,'dates':'2026-03-30_to_2026-04-13','focus':'DAgger_run8_complete+run9_launch','goals':['run8_6_iters_done','eval_20_eps','launch_run9_corrected_beta','push_1000_milestone_services'],'velocity_services_per_day':30}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
