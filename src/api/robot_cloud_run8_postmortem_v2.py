import datetime,fastapi,uvicorn
PORT=8773
SERVICE="robot_cloud_run8_postmortem_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/postmortem")
def postmortem(): return {"run":8,"outcome":"SUCCESS_100pct_SR",
  "surprise":"100%_SR_despite_beta_decay_bug_collapsing_DAgger_signal",
  "hypothesis":"299_on_policy_episodes_enough_to_converge_even_without_expert_correction",
  "beta_decay_bug":"0.30->0.009->0.0003->~0 (multiplier 0.03 not additive)",
  "server_readiness_bug":"fixed_in_commit_3c61f52fe4",
  "run9_purpose":"confirm_100%_SR_robust_and_generalizes"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
