import datetime,fastapi,uvicorn
PORT=8327
SERVICE="training_cluster_api"
DESCRIPTION="Training cluster management API"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/cluster')
def c(): return {'nodes':1,'gpus_per_node':8,'gpu_model':'A100_80GB','interconnect':'NVLink_NVSwitch','storage_tb':100,'os':'Ubuntu_22.04','cuda':'12.1','pytorch':'2.3'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
