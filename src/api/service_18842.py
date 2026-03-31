import datetime,fastapi,uvicorn
PORT=18842
SERVICE="n3_project_infra"
DESCRIPTION="N3 infra: H100 SXM 80GB × 4 per pod — $18.20/hr on OCI GPU4 — 4x A100 cost — premium tier"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
