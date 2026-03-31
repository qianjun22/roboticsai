import datetime,fastapi,uvicorn
PORT=25472
SERVICE="rl_ppo_genesis_usage"
DESCRIPTION="Genesis usage for PPO: 100k episodes x 30s each = 3M sim seconds -- Genesis 100k steps/sec = 30min -- feasible"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
