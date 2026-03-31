import datetime,fastapi,uvicorn
PORT=21372
SERVICE="aiworld_prep_sep1_morning"
DESCRIPTION="Sep 1 morning: Jun's 20-min talk slot at 10am -- 150 registered attendees -- 'OCI Robot Cloud: 70% SR'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
