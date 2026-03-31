import datetime,fastapi,uvicorn
PORT=16494
SERVICE="run9_finetune_450"
DESCRIPTION="Run9 fine-tune 450: starts ~11:00 UTC — 300min at 1.5it/s → ckpt-7000 ~16:00 UTC"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
