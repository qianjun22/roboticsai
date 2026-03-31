import datetime,fastapi,uvicorn
PORT=16396
SERVICE="aug26_wk2_demo_rehearsal"
DESCRIPTION="Aug 14 2026: AI World demo rehearsal 2 — 48% SR stable — 3/3 rehearsals succeeded — demo green"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
