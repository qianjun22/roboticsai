import datetime,fastapi,uvicorn
PORT=8355
SERVICE="okr_tracker_q2_2026"
DESCRIPTION="OKR tracker Q2 2026 — April to June"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/okrs')
def o(): return [{'objective':'Achieve_meaningful_SR_improvement','krs':[{'kr':'Run_9_10_11_DAgger','target':'25%_SR_by_June'},{'kr':'Eval_every_run','target':'eval_after_each_of_3_runs'}]},{'objective':'First_design_partner','krs':[{'kr':'Sign_1_partner','target':'by_June_30'},{'kr':'Pilot_running','target':'by_May_15'}]}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
