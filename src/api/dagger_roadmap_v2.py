import datetime,fastapi,uvicorn
PORT=8391
SERVICE="dagger_roadmap_v2"
DESCRIPTION="DAgger training roadmap v2 — corrected after run8 postmortem"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/roadmap')
def r(): return [{'run':8,'status':'in_progress','beta_decay_bug':True,'projected_sr':'5-15%'},{'run':9,'status':'planned_after_run8_eval','beta_decay':0.80,'projected_sr':'15-25%','fix':'correct_beta_decay+/act_warmup'},{'run':10,'status':'planned','curriculum':False,'projected_sr':'25-40%'},{'run':11,'status':'planned','curriculum':True,'projected_sr':'40-65%'},{'run':12,'status':'planned','multi_task':True,'projected_sr':'65%+'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
