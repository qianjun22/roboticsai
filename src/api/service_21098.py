import datetime,fastapi,uvicorn
PORT=21098
SERVICE="origin_full_single_line"
DESCRIPTION="Single line: '5% to 90% SR, $0 to $500M ARR, 1 to 200 people -- 3 years, 1 OCI A100, 1 bet.'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
