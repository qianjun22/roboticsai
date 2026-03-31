import datetime,fastapi,uvicorn
PORT=15271
SERVICE="ai_world_day1"
DESCRIPTION="AI World Day 1: Sep 23 2026, booth setup, Jun's talk 2pm — 'DAgger + GR00T: 48% SR on OCI'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
