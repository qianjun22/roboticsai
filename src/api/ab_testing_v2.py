import datetime,fastapi,uvicorn
PORT=8330
SERVICE="ab_testing_v2"
DESCRIPTION="A/B testing framework v2 — policy comparison"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/framework')
def f(): return {'method':'Thompson_sampling','traffic_split_pct':[50,50],'metrics_primary':'SR','metrics_secondary':['latency','episode_length'],'min_episodes_per_variant':50,'auto_promote_winner':True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
