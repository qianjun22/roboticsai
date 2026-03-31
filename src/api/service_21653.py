import datetime,fastapi,uvicorn
PORT=21653
SERVICE="q3_2026_oct_hiring"
DESCRIPTION="Oct 2026: hire 3 more -- ML Eng 3, Sales 1, CS 1 -- team of 7 -- growing fast on Series A funds"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
