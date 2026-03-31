import datetime,fastapi,uvicorn
PORT=20881
SERVICE="unit_econ_cogs_training"
DESCRIPTION="COGS training: A100 $3.22/hr x 35min = $1.88/training run -- 50k runs/yr = $94k -- low fixed cost"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
