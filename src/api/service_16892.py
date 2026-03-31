import datetime,fastapi,uvicorn
PORT=16892
SERVICE="infra_alerting_rules"
DESCRIPTION="Alerting rules: GPU OOM, fine-tune stuck >2h, SR drop >5pp, latency p99 >500ms — PagerDuty"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
