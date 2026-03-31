import datetime,fastapi,uvicorn
PORT=22855
SERVICE="fin_ltm_q4"
DESCRIPTION="LTM Q4 2029: $500M ARR, 82% GM, 35% EBITDA -- public company financial profile -- IPO thesis"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
