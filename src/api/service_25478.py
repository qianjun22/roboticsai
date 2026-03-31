import datetime,fastapi,uvicorn
PORT=25478
SERVICE="rl_ppo_jun_view"
DESCRIPTION="Jun on RL: 'PPO adds 5pp SR at 10x cost. For BMW, that 5pp is worth it. For SMB, DAgger is enough.'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
