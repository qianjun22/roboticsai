import datetime,fastapi,uvicorn
PORT=16041
SERVICE="wrist_cam_realsense_spec"
DESCRIPTION="RealSense D435: 640×480 depth at 30fps, 1280×720 RGB, 87-degree FOV, USB3.0 Gen1, 20g weight"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
