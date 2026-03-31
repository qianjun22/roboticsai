import datetime,fastapi,uvicorn
PORT=14263
SERVICE="icra2027_experiments"
DESCRIPTION="ICRA 2027 experiments: run9 (35%) vs run10 (48%) vs run10-no-wrist (38%) — wrist cam +10pp"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
