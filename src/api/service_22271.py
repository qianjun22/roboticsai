import datetime,fastapi,uvicorn
PORT=22271
SERVICE="ebitda_rule_of_40"
DESCRIPTION="Rule of 40: ARR growth (150% in 2027) + EBITDA margin (-133%) = 17 -- below 40 -- growth phase"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
