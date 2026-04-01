import datetime,fastapi,uvicorn
PORT=8376
SERVICE="oci_budget_tracker"
DESCRIPTION="OCI compute budget tracker"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/budget')
def b(): return {'monthly_allocation_usd':5000,'ytd_spend_usd':3200,'gpu_hours_used':320,'gpu_hours_allocated':500,'cost_breakdown':{'dagger_training':0.43,'inference_server':1.2,'sdg_generation':0.8,'storage':0.15},'utilization_pct':64}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
