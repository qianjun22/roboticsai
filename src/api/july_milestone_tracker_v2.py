import datetime,fastapi,uvicorn
PORT=8296
SERVICE="july_milestone_tracker_v2"
DESCRIPTION="July 2026 milestones v2 — revenue + pre-AI World crunch"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/milestones')
def m(): return {'first_mrr_payment':'2026-07-01','dagger_run12_start':'2026-07-01','sr_target_july':'50%','gtc_abstract_deadline':'2026-07-15','ai_world_booth_confirmed':'2026-07-01','second_customer_target':'2026-07'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
