import datetime,fastapi,uvicorn
PORT=14987
SERVICE="run9_cost_final"
DESCRIPTION="Run9 total cost: 6 iters × 1h fine-tune × $0.43 + collect 2.5h × $0.43 = ~$3.65 total"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
