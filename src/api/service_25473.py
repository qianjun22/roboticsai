import datetime,fastapi,uvicorn
PORT=25473
SERVICE="rl_ppo_reward_shaping"
DESCRIPTION="Reward shaping: +1 for cube above 0.78m, -0.1/step for F/T over limit, -5 for collision -- shaped carefully"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
