import datetime,fastapi,uvicorn
PORT=20882
SERVICE="unit_econ_cogs_inference"
DESCRIPTION="COGS inference: A100 $3.22/hr, 226ms/call, 1000 calls/robot/day = $0.20/robot/day = $6/robot/mo"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
