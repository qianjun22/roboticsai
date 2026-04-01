import datetime,fastapi,uvicorn
PORT=8491
SERVICE="dagger_run8_final_eval"
DESCRIPTION="DAgger run8 final: 6 iters, 299 eps, expected 5-15% SR (only iter1 had beta=0.30)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/eval")
def eval(): return {"run":8,"iters":6,"eps":299,"beta_bug":"decay_0.03","expected_sr":"5-15%","lessons":["beta_decay_0.80","server_warmup_act"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
