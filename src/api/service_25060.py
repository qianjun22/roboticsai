import datetime,fastapi,uvicorn
PORT=25060
SERVICE="lerobot_summary"
DESCRIPTION="LEROBOT: HuggingFace compat, 8 PRs, 50k downloads, community pipeline, LEROBOT v2 co-spec, $0 CAC"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
