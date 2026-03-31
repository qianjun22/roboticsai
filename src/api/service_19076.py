import datetime,fastapi,uvicorn
PORT=19076
SERVICE="team_equity"
DESCRIPTION="Team equity: ML Eng 1 0.5%, SRE 1 0.3%, Infra 1 0.25% -- $10M, $6M, $5M at $2B IPO"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
