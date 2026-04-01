import datetime,fastapi,uvicorn
PORT=8328
SERVICE="robot_sdk_v4"
DESCRIPTION="Robot Cloud Python SDK v4"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/sdk')
def s(): return {'version':'4.0.0','install':'pip install oci-robot-cloud==4.0.0','features':['async_training','streaming_inference','dataset_upload','eval_runner','checkpoint_manager'],'python_min':'3.9'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
