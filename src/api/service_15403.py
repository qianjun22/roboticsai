import datetime,fastapi,uvicorn
PORT=15403
SERVICE="run15_ppo_config"
DESCRIPTION="Run15 PPO config: lr=3e-5, clip=0.2, entropy=0.01, 2048 steps/update, 8 parallel envs Isaac"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
