import datetime,fastapi,uvicorn
PORT=8276
SERVICE="open_source_sdk_v4"
DESCRIPTION="OCI Robot Cloud open source SDK v4 — developer-first"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/sdk')
def sdk(): return {'version':'4.0','install':'pip install oci-robot-cloud','github':'qianjun22/roboticsai','stars_target':500,'languages':['python','javascript'],'docs':'robot.cloud/docs'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
