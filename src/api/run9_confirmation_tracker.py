import datetime,fastapi,uvicorn
PORT=8831
SERVICE="run9_confirmation_tracker"
DESCRIPTION="DAgger run9 confirmation — validating 100% SR robustness with beta_decay=0.80"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/status")
def status(): return {"run":9,"status":"running","iters":6,"eps_per_iter":75,"beta_start":0.40,"beta_decay":0.80,"base_model":"run8_iter6_ckpt5000","goal":"confirm 100pct SR robustness","notes":"first run with correct beta_decay=0.80 (not 0.03)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
