import datetime,fastapi,uvicorn
PORT=19145
SERVICE="unit_econ_cogs_gpu"
DESCRIPTION="COGS GPU: A100 $0.43/run x 50 runs/mo x 1 robot = $21.5/robot/mo -- 0.14% of $15k"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
