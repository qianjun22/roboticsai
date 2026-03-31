import datetime,fastapi,uvicorn
PORT=19409
SERVICE="run9_cost"
DESCRIPTION="Run9 cost: 450 demos x $2.50 + 6 iters x 5000 steps x $0.043/step = $1,125 + $1,290 = $2,415"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
