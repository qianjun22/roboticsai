import datetime,fastapi,uvicorn
PORT=26235
SERVICE="ipo_lockup_end"
DESCRIPTION="Lockup end: Sep 2028 -- Jun sells 5% of holdings -- $58M pre-tax -- first liquidity in 2.5yr -- reinvests"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
