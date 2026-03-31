import datetime,fastapi,uvicorn
PORT=25420
SERVICE="failure_taxonomy_summary"
DESCRIPTION="Failure taxonomy: 5 classes, 35% grasp, wrist cam fixes Class 1+3, F/T fixes Class 4, IROS 2028, product use"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
