import datetime,fastapi,uvicorn
PORT=22752
SERVICE="aiworld_greg_notification"
DESCRIPTION="8:45pm: Jun emails Greg Pavlik -- 'BMW LOI received. $150k/mo. OCI RC is working.' -- Greg responds 11pm"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
