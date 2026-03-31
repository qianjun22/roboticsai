import datetime,fastapi,uvicorn
PORT=20570
SERVICE="aug26_ops_aug20_bmw_demo"
DESCRIPTION="Aug 20: BMW R&D Zoom demo -- Jun runs robot live -- 6/10 in 15min -- Dieter: 'impressive for 6 months'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
