import datetime,fastapi,uvicorn
PORT=8388
SERVICE="community_events_tracker"
DESCRIPTION="Community events tracker — meetups, workshops, hackathons"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/events')
def e(): return [{'event':'OCI_Robotics_Hackathon','date':'2026-08-01','format':'virtual','prize_pool_usd':5000,'target_participants':50},{'event':'GR00T_DAgger_Workshop','date':'GTC_2027_co_located','format':'half_day','capacity':100}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
