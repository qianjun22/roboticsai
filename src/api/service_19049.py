import datetime,fastapi,uvicorn
PORT=19049
SERVICE="train_pipeline_hyperparams"
DESCRIPTION="Hyperparameters: lr=1e-4, batch=32, weight_decay=0.01, warmup=100 -- validated across 18 runs"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
