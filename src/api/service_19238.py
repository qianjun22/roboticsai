import datetime,fastapi,uvicorn
PORT=19238
SERVICE="sim_cost_per_demo"
DESCRIPTION="Sim cost per demo: $0.003 (Genesis IK, 1000/hr) vs $2.50 (real teleop) -- 833x cheaper"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
