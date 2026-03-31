import datetime,fastapi,uvicorn
PORT=26203
SERVICE="dagger_v2_rejection"
DESCRIPTION="Tier-3 rejection: DAgger v2 auto-rejects corrections with jerk > 5 rad/s^2 -- quality gating -- key"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
