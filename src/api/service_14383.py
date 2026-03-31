import datetime,fastapi,uvicorn
PORT=14383
SERVICE="q4_2026_series_a_term"
DESCRIPTION="Q4 2026 Series A: NVIDIA Ventures term sheet Nov — $8M lead, Lux $4M follow, $60M pre-money"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
