import datetime,fastapi,uvicorn
PORT=25891
SERVICE="franka_realsense_wrist"
DESCRIPTION="Wrist cam upgrade 2027: RealSense D455 -- 90fps -- 1280x720 -- 3pp SR improvement -- crisp feedback"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
