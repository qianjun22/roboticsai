import datetime,fastapi,uvicorn
PORT=24232
SERVICE="fleet_50k_energy"
DESCRIPTION="Energy: 50k robots x 0.8kW avg x 8hr per day = 3.2GWh per day -- OCI RC tracks carbon per robot"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
