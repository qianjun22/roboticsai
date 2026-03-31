import datetime,fastapi,uvicorn
PORT=20471
SERVICE="may26_ops_nimble_demo_live"
DESCRIPTION="May 12 3pm: Nimble demo -- Jun runs robot live on Zoom -- 5/10 in demo -- Marcus: 'impressive'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
