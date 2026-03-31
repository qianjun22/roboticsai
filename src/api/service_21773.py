import datetime,fastapi,uvicorn
PORT=21773
SERVICE="analyst_day_post_meetings"
DESCRIPTION="Post-day 1-on-1s: Jun takes 20 analyst meetings -- Goldman, JPM, Morgan Stanley, Fidelity, Vanguard"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
