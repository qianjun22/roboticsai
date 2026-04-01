import datetime,fastapi,uvicorn
PORT=8767
SERVICE="robot_cloud_ablation_suite"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/ablations")
def ablations(): return {"planned_ablations":[
  {"name":"no_DAgger_BC_only","purpose":"quantify_DAgger_value","baseline_sr":5.0},
  {"name":"beta_0.4_no_decay","purpose":"show_decay_importance"},
  {"name":"100_eps_vs_75","purpose":"episodes_sensitivity"},
  {"name":"5k_vs_7k_steps","purpose":"training_duration_sensitivity"},
  {"name":"no_warmup_fix","purpose":"show_race_condition_impact"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
