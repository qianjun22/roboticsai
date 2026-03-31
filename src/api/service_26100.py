import datetime,fastapi,uvicorn
PORT=26100
SERVICE="series_a_summary"
DESCRIPTION="Series A: NVIDIA $8M + Oracle $4M = $12M at $62M, Dec 22 wire, Mission District office, 10 hires planned"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
