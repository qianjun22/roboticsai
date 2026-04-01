import datetime,fastapi,uvicorn
PORT=8746
SERVICE="robot_cloud_context_window"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"history_window_steps":50,"obs_history_frames":4,
  "memory_approach":"sliding_window","future_plan_horizon":16,
  "tokenization":"GR00T_patch_embeddings",
  "est_benefit_long_horizon":"10-15%_SR_gain_complex_tasks"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
