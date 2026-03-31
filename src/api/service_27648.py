import datetime,fastapi,uvicorn
PORT=27648
SERVICE="n6_compute_cost"
DESCRIPTION="N6 compute: OCI H200 cluster -- $5.20/hr -- inference cost $0.0068/correction (vs N5 $0.0053) -- 28% up"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
