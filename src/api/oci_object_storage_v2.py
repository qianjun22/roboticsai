import datetime,fastapi,uvicorn
PORT=8371
SERVICE="oci_object_storage_v2"
DESCRIPTION="OCI Object Storage integration v2 — checkpoints + datasets"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def c(): return {'namespace':'roboticsai','bucket_checkpoints':'groot-checkpoints','bucket_datasets':'robot-demos','bucket_logs':'training-logs','region':'us-ashburn-1','versioning':True,'lifecycle_90d_archive':True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
