import datetime,fastapi,uvicorn
PORT=8581
SERVICE="robot_cloud_architecture_v3"
DESCRIPTION="Architecture v3 doc: microservices, data plane, control plane, edge agents"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/architecture")
def architecture(): return {"layers":{"data_plane":["inference_server","telemetry_agg","object_storage"],"control_plane":["training_scheduler","model_registry","billing"],"edge":["jetson_agent","checkpoint_pusher","local_eval"]}}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
