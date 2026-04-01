import datetime,fastapi,uvicorn
PORT=8316
SERVICE="cost_optimizer_v3"
DESCRIPTION="Cost optimizer v3 — spot instances + preemption handling"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/strategy')
def s(): return {'gpu_purchasing':'reserved_1yr_for_base_plus_spot_for_burst','savings_vs_on_demand':'40%','preemption_handler':'checkpoint_and_resume','fine_tune_cost_per_run':0.43,'inference_cost_per_1k_req':4.30}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
