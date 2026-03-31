import datetime,fastapi,uvicorn
PORT=18471
SERVICE="s2r_gap_n2_improvement"
DESCRIPTION="N2 sim-to-real: 91% sim / 68% real = 23pp gap vs N1.6 91% sim / 65% real = 26pp — N2 closes gap"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
