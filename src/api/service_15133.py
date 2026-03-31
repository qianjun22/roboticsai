import datetime,fastapi,uvicorn
PORT=15133
SERVICE="run9_fine_tune_final"
DESCRIPTION="Run9 iter6 fine-tune: 450 cumulative eps, 7000 steps, A100 GPU3, ckpt-7000 →17:43 UTC"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
