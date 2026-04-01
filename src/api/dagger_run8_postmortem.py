import datetime,fastapi,uvicorn
PORT=8283
SERVICE="dagger_run8_postmortem"
DESCRIPTION="DAgger run 8 postmortem — server readiness + beta decay bugs"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/postmortem')
def postmortem(): return {'bugs':['server_health_check_before_model_loads','beta_decay_0.03_collapses_too_fast'],'fixes':['added_/act_warmup_query_after_/health','next_run_use_beta_decay=0.80'],'impact':'only_iter1_had_true_dagger_signal','projected_sr':'5-15%_vs_5%_baseline','lesson':'always_validate_/act_not_just_/health'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
