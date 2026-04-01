import datetime,fastapi,uvicorn
PORT=8321
SERVICE="system_architecture_v2"
DESCRIPTION="System architecture v2 — full stack overview"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/arch')
def a(): return {'layers':{'data':'Genesis_SDG+customer_demos','training':'GR00T_finetune+DAgger','serving':'FastAPI_inference_server','orchestration':'OCI_Functions+Kubernetes','storage':'OCI_Object_Storage+NFS'},'gpu_fleet':'8xA100_80GB','github':'qianjun22/roboticsai'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
