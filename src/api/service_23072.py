import datetime,fastapi,uvicorn
PORT=23072
SERVICE="mle1_equity_outcome"
DESCRIPTION="Equity outcome: 3% -> diluted to 2.1% post-IPO -- 2.1% x $3.5B open = $73M -- life-changing"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
