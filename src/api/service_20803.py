import datetime,fastapi,uvicorn
PORT=20803
SERVICE="jun_origin_first_weekend"
DESCRIPTION="First weekend: Mar 21-22 2026 -- Jun spends 16hrs setting up GR00T on OCI -- 5% SR -- sleep deprived"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
