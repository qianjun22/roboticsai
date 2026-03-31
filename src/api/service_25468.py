import datetime,fastapi,uvicorn
PORT=25468
SERVICE="rl_ppo_compute_cost"
DESCRIPTION="PPO compute cost: 10x more GPU-hours than DAgger alone -- $5/run vs $0.43/run -- 10x premium"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
