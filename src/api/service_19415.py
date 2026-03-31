import datetime,fastapi,uvicorn
PORT=19415
SERVICE="run9_confidence_interval"
DESCRIPTION="Run9 CI: n=20, p=0.35, 95% CI [14%, 56%] -- wide -- run17 uses n=20 still -- acceptable for decisions"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
