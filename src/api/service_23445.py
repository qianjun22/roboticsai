import datetime,fastapi,uvicorn
PORT=23445
SERVICE="gpu_economics_training_run"
DESCRIPTION="Training run cost: 35min fine-tune on A100 = $1.88 OCI vs $2.40 AWS -- $0.52 savings per run"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
