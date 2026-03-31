import datetime,fastapi,uvicorn
PORT=18847
SERVICE="n3_project_cost"
DESCRIPTION="N3 fine-tune cost: $18.20/hr × 85min/60 = $2.58 per run — 6x N1.6 but SR justifies premium tier"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
