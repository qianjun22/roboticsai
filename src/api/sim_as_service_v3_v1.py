import datetime,fastapi,fastapi.responses,uvicorn
PORT=9475
SERVICE="sim_as_service_v3"
DESCRIPTION="Simulation-as-a-Service v3 Isaac cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/sim-as-service-v3")
def domain(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT,"status":"active"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
