import datetime,fastapi,uvicorn
PORT=21390
SERVICE="run9_demo_recollect"
DESCRIPTION="Demo recollection Jun 9: 100 new demos with wrist cam -- 3 operators, 33 each -- SpaceMouse + wrist view"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
