import datetime,fastapi,uvicorn
PORT=17979
SERVICE="onboard_cost_estimate"
DESCRIPTION="Cost estimate: $0.43/fine-tune run, 6 iters × $0.43 = $2.58 DAgger — explained at onboarding"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
