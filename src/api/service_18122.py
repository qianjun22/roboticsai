import datetime,fastapi,uvicorn
PORT=18122
SERVICE="hardware_kuka"
DESCRIPTION="KUKA iiwa: 7DOF, 0.8m reach, 14kg payload, KUKA FRI — BMW's robot — URDF adapter written Q3 2026"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
