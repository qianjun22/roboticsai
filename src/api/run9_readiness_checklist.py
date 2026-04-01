import datetime,fastapi,uvicorn
PORT=8402
SERVICE="run9_readiness_checklist"
DESCRIPTION="DAgger run9 readiness checklist"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/checklist')
def c(): return [{'item':'run8_eval_complete','status':'pending'},{'item':'server_readiness_fix_committed','status':'done','commit':'3c61f52fe4'},{'item':'beta_decay_corrected_0.80','status':'done','file':'src/training/dagger_run9_launch.sh'},{'item':'base_model_path_set','status':'pending','note':'use_run8_best_checkpoint'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
