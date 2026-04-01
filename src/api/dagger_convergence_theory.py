import datetime,fastapi,uvicorn
PORT=8949
SERVICE="dagger_convergence_theory"
DESCRIPTION="DAgger convergence theory — why run8 converged to 100pct despite beta collapse"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/theory")
def theory(): return {"observation":"run8 100pct SR despite only iter1 having DAgger signal","hypothesis1":"GR00T N1.6 is already near-capable; 1 iter of 50 on-policy eps sufficient to bridge gap","hypothesis2":"299 total BC episodes post-iter1 gave sufficient state coverage","hypothesis3":"cube_pick is a simple enough task that 1 DAgger correction iter is sufficient","evidence_for":["fast convergence in iter1 (loss dropped from 0.35 to 0.18)","run9 likely to confirm"],"implication":"simple manipulation tasks may need <100 on-policy episodes","complexity_hypothesis":"harder tasks (cube_stack, assembly) will need more DAgger iters"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
