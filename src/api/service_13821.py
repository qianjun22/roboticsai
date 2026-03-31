import datetime,fastapi,uvicorn
PORT=13821
SERVICE="gtm_icp_definition"
DESCRIPTION="GTM ICP definition: Series B+ robotics cos, 10-200 robots, Franka/UR5/xArm, NVIDIA Isaac users"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
