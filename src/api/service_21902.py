import datetime,fastapi,uvicorn
PORT=21902
SERVICE="humanoid_agility_digit"
DESCRIPTION="Agility Digit: bipedal, 2-arm, 20-DOF -- $250k/unit -- Digit v4 supports OCI RC integration"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
