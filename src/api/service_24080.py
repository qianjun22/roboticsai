import datetime,fastapi,uvicorn
PORT=24080
SERVICE="deal_anatomy_summary"
DESCRIPTION="$1M deal anatomy: NVIDIA ref -> pilot -> 22pp gain -> 200 arms -> 2yr $1.8M -> wrist cam -> $1.5M yr2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
