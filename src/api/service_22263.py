import datetime,fastapi,uvicorn
PORT=22263
SERVICE="ebitda_2028_improving"
DESCRIPTION="2028 EBITDA: -$10M -- $42M ARR midyear, 78% GM = $33M gross -- $43M opex (team 80) -- improving"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
