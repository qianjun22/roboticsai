import datetime,fastapi,uvicorn
PORT=17136
SERVICE="nov26_team_5"
DESCRIPTION="Nov 2026 team 5: Jun + ML eng 1 + SRE 1 + AE 1 + ops contractor — next: ML eng 2 + SRE 2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
