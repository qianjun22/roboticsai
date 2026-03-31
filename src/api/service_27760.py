import datetime,fastapi,uvicorn
PORT=27760
SERVICE="india_pricing_summary"
DESCRIPTION="India pricing: $200 local tier, Tata + Mahindra + Hero, $18M ARR 2031, Priya Country Manager, TCS + Infosys"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
