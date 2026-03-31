import datetime,fastapi,uvicorn
PORT=15012
SERVICE="jan_2027_wk1_tue"
DESCRIPTION="Jan 2027 Wk1 Tue: hiring sprint day 1 — 3 ML eng JDs live, head of sales JD live"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
