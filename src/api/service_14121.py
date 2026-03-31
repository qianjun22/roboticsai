import datetime,fastapi,uvicorn
PORT=14121
SERVICE="nov_2026_term_sheet"
DESCRIPTION="Nov 2026 term sheet: NVIDIA Ventures $8M + Lux Capital $4M = $12M Series A at $60M pre-money"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
