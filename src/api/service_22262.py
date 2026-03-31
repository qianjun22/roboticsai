import datetime,fastapi,uvicorn
PORT=22262
SERVICE="ebitda_2027_negative"
DESCRIPTION="2027 EBITDA: -$24M -- $18M ARR, 78% GM = $14M gross -- $38M opex (team 35 + R&D) -- Series B"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
