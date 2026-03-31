import datetime,fastapi,uvicorn
PORT=22267
SERVICE="ebitda_opex_leverage"
DESCRIPTION="Opex leverage: $6.3M (35 people 2027) -> $36M (200 people 2029) but ARR grows 28x -- ratio improves"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
