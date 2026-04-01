import datetime,fastapi,uvicorn
PORT=8403
SERVICE="dagger_v2_architecture"
DESCRIPTION="DAgger v2 architecture — improvements for run9+"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/improvements')
def i(): return [{'fix':'beta_decay=0.80_vs_0.03','impact':'meaningful_DAgger_signal_all_iters'},{'fix':'/act_warmup_after_/health','impact':'no_empty_JSON_responses'},{'fix':'eval_50_eps_not_20','impact':'lower_variance_SR_estimates'},{'fix':'increase_episodes_to_75','impact':'more_diverse_data_per_iter'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
