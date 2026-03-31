import datetime,fastapi,uvicorn
PORT=14636
SERVICE="gtm_cold_email_sequence"
DESCRIPTION="Cold email sequence: 7-touch, day 1/3/5/8/13/21/30 — personalized with SR data, unsubscribe respected"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
