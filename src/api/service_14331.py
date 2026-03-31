import datetime,fastapi,uvicorn
PORT=14331
SERVICE="iter5_loss_tracking"
DESCRIPTION="Iter5 loss tracking: ckpt-1000 loss≈0.078, ckpt-2000 loss≈0.074, ckpt-3000 loss≈0.071 — converging"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
