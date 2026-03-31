import datetime,fastapi,uvicorn
PORT=26928
SERVICE="india_arr_2031"
DESCRIPTION="India ARR 2031: Tata + Mahindra + L&T + 8 others = $12M ARR -- small but growing -- long-term market"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
