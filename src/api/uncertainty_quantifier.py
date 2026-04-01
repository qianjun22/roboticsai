import datetime,fastapi,uvicorn
PORT=8363
SERVICE="uncertainty_quantifier"
DESCRIPTION="Model uncertainty quantification — know when to ask for help"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/methods')
def m(): return {'method':'ensemble_disagreement','n_models':5,'threshold':0.15,'action':'defer_to_human_when_uncertainty_high','current_uncertainty':'not_measured_yet','use_case':'safety_critical_handoffs'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
