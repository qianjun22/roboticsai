import datetime,fastapi,uvicorn
PORT=8759
SERVICE="robot_cloud_imitation_gap"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/gap_analysis")
def gap_analysis(): return {"covariate_shift_issue":"BC_fails_on_unseen_states",
  "dagger_fixes":"queries_expert_on_policy_states",
  "remaining_gap":["long_horizon_compounding","multi_step_planning","novel_objects"],
  "our_mitigation":"curriculum+lang_cond+cosmos_world_model"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
