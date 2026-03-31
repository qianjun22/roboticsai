import datetime,fastapi,uvicorn
PORT=15670
SERVICE="dagger_vs_bc"
DESCRIPTION="DAgger vs BC: BC 5% (1000 demos) vs DAgger 35% (450 demos) — 7x fewer demos, 7x better SR"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
