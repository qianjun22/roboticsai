import datetime,fastapi,uvicorn
PORT=21989
SERVICE="milestone_22000_key_hardware"
DESCRIPTION="Key hardware: Franka Research 3, RealSense D435, ATI Mini45, SpaceMouse, OCI A100, OCI H100"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
