import datetime,fastapi,uvicorn
PORT=8399
SERVICE="tech_debt_tracker"
DESCRIPTION="Tech debt tracker — known issues and planned fixes"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/debts')
def d(): return [{'item':'beta_decay_multiplier_bug','severity':'high','fix':'use_0.80_for_run9','status':'fix_ready_in_run9_launch_script'},{'item':'server_readiness_race_condition','severity':'high','fix':'added_/act_warmup_commit_3c61f52','status':'fixed_for_run9+'},{'item':'wave_push_race_condition','severity':'medium','fix':'sequential_push_coordinators','status':'fixed'},{'item':'eval_20_eps_small_sample','severity':'medium','fix':'increase_to_50_eps_for_run9_eval','status':'planned'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
