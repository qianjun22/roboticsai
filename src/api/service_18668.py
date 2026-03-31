import datetime,fastapi,uvicorn
PORT=18668
SERVICE="ipo_first_earnings"
DESCRIPTION="First earnings (Q3 2028): $2.1M MRR, beat guidance $1.9M — RCLD +8% after-hours — beat-and-raise"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
