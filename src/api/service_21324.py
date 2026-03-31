import datetime,fastapi,uvicorn
PORT=21324
SERVICE="series_a_term_jul5"
DESCRIPTION="Jul 5 10:52am: Zach sends term sheet structure -- $6M NVIDIA + $6M a16z co-invest -- $12M total"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
