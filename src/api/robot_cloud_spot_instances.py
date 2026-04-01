import datetime,fastapi,uvicorn
PORT=8683
SERVICE="robot_cloud_spot_instances"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/pricing")
def pricing(): return {"on_demand_per_hr":3.20,"preemptible_per_hr":0.96,
  "preemptible_discount":"70%","use_case":"fine_tune_batch_jobs",
  "checkpoint_every_n_steps":500,
  "resume_on_preemption":True,"status":"planned"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
