import datetime,fastapi,uvicorn
PORT=8342
SERVICE="greg_pavlik_brief"
DESCRIPTION="Greg Pavlik (Oracle CTO) executive brief — OCI Robot Cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/brief')
def b(): return {'audience':'Greg_Pavlik_Oracle_CTO','key_ask':'NVIDIA_relationship_intro+official_OCI_product_license','one_liner':'NVIDIA_trains_model_Oracle_trains_robot','proven_results':{'mae_improvement':'8.7x','inference_latency_ms':226,'cost_savings_vs_aws':'9.6x'},'budget_ask':0,'timeline_to_revenue':'Sept_2026'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
