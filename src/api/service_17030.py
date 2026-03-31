import datetime,fastapi,uvicorn
PORT=17030
SERVICE="jun26_arXiv_abstract"
DESCRIPTION="arXiv abstract: BC 5% → DAgger 35% → wrist cam 48% — 9.6x cheaper than AWS — open-source SDK"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
