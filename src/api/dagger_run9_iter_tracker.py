import datetime,fastapi,uvicorn
PORT=8858
SERVICE="dagger_run9_iter_tracker"
DESCRIPTION="DAgger run9 iteration tracker — beta decay schedule and convergence monitoring"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/iters")
def iters(): return {"run":9,"config":{"beta_start":0.40,"beta_decay":0.80,"iters":6,"eps_per_iter":75,"steps_per_iter":7000},"beta_schedule":{"iter1":0.40,"iter2":0.32,"iter3":0.256,"iter4":0.205,"iter5":0.164,"iter6":0.131},"diverged_steps_per_ep":{"iter1":"25-42 (active DAgger signal)","iter2":"est 15-30","iter3":"est 10-20","iter4-6":"est 5-15 (policy improving)"},"total_episodes":450,"status":"iter1/6 collecting"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
