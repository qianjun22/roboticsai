import datetime,fastapi,uvicorn
PORT=19252
SERVICE="run_sr_chart"
DESCRIPTION="SR chart: BC 5 - R9 35 - R10 48 - R11 55 - R12 60 - R13 64 - R14 67 - R15 70 - R16-17 81 - R18 90"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
