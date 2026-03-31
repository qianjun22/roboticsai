import datetime,fastapi,uvicorn
PORT=18881
SERVICE="may_week1_plan"
DESCRIPTION="May 2026 week 1 plan: DAgger iter1 -- 75 demos, 5000 steps, eval target 15% -- DAgger hypothesis"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
