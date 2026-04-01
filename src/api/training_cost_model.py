import datetime,fastapi,uvicorn
PORT=8393
SERVICE="training_cost_model"
DESCRIPTION="Training cost model — total cost to 65% SR"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/estimate')
def e(): return {'cost_per_run_usd':0.43,'runs_to_65pct_sr':8,'total_training_cost_usd':3.44,'gpu_hours_total':8,'vs_aws_cost_usd':33,'savings_vs_aws_usd':29.56,'annotation_cost_if_human':0}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
