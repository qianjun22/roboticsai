import datetime,fastapi,uvicorn
PORT=25880
SERVICE="founding_2026_summary"
DESCRIPTION="2026 summary: Mar GR00T -> Apr 70% SR -> May Nimble+Oracle -> Jun HN -> Aug hire+resign -> Sep BMW -> Dec $12M"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
