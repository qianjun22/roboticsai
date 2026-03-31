import datetime,fastapi,uvicorn
PORT=20583
SERVICE="run16_n2_infra"
DESCRIPTION="Run16 infra: OCI H100 80GB x 2 per pod -- $8.40/hr -- DDP training -- 2x A100 cost -- justified"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
