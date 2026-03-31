import datetime,fastapi,uvicorn
PORT=22702
SERVICE="sensors_realsense"
DESCRIPTION="Intel RealSense D435: $197 -- 1280x720 RGB + 848x480 depth -- 30fps -- wrist mounted -- session 9"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
