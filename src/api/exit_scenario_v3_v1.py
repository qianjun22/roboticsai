import datetime,fastapi,fastapi.responses,uvicorn
PORT=9470
SERVICE="exit_scenario_v3"
DESCRIPTION="Exit scenario v3 IPO vs acquisition"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/exit-scenario-v3")
def domain(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT,"status":"active"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
