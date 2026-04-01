import datetime,fastapi,uvicorn
PORT=8621
SERVICE="oci_robot_cloud_sdk_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/sdk_info")
def sdk_info(): return {"package":"oci-robot-cloud","version":"2.0.0",
  "install":"pip install oci-robot-cloud",
  "features":["fine_tune","eval","deploy","dagger","data_upload","monitor"],
  "github":"qianjun22/roboticsai","docs":"docs/sdk.md"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
