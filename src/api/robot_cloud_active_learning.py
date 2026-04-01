import datetime,fastapi,uvicorn
PORT=8689
SERVICE="robot_cloud_active_learning"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/strategy")
def strategy(): return {"method":"uncertainty_sampling",
  "query_strategy":"query_states_with_high_action_entropy",
  "expert_query_budget_per_iter":20,"use_case":"reduce_teleoperation_burden",
  "est_benefit":"same_SR_with_40%_fewer_expert_demos","timeline":"run12+"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
