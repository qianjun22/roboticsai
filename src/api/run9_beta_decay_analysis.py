import datetime,fastapi,uvicorn
PORT=8942
SERVICE="run9_beta_decay_analysis"
DESCRIPTION="Run9 beta decay analysis — correct 0.80 decay vs run8 buggy 0.03 decay"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/analysis")
def analysis(): return {"run8_bug":{"beta_decay":0.03,"actual_behavior":"multiplier not exponent -> 0.30*0.03=0.009 after iter1","effective_iters_with_signal":1,"result":"100pct SR (surprising - BC on 299 eps enough)"},"run9_fix":{"beta_decay":0.80,"schedule":[0.40,0.32,0.256,0.205,0.164,0.131],"all_iters_have_signal":True,"diverged_steps_expected":"25-40 through all iters"},"hypothesis":"run9 SR >= run8 (100pct) with more robust convergence","implication":"if run9 also 100pct, DAgger converges fast from run8 baseline"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
