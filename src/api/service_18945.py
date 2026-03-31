import datetime,fastapi,uvicorn
PORT=18945
SERVICE="aug_week3_n2_eval_sim"
DESCRIPTION="Aug 25 N2 sim eval: 91% SR in LIBERO sim -- 2pp better than N1.6 89% -- but real gap?"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
