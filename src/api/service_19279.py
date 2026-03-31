import datetime,fastapi,uvicorn
PORT=19279
SERVICE="post_ipo_what_it_took"
DESCRIPTION="What it took: 1 insight (DAgger+GR00T+OCI), 1 experiment (BC 5%), 1 commitment, 3 years"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
