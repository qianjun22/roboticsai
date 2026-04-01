import datetime,fastapi,uvicorn
PORT=8282
SERVICE="dagger_beta_analysis"
DESCRIPTION="DAgger beta decay analysis — run8 postmortem"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/analysis')
def analysis(): return {'run8_issue':'beta_decay=0.03 as multiplier collapses beta to 0.01 after iter1','iter1_beta':0.30,'iter2_beta':0.009,'iter3_beta':0.0003,'fix':'use beta_decay=0.80 (mild) or beta_decay=subtract_0.05','impact':'iters_2-6_were_essentially_pure_BC_not_DAgger'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
