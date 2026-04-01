import datetime,fastapi,uvicorn
PORT=8605
SERVICE="nvidia_gtc2027_prep"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/status")
def status(): return {"event":"GTC 2027","date":"2027-03-17",
  "talk_title":"OCI Robot Cloud: From 5% to 75% Closed-Loop SR with DAgger on OCI A100",
  "abstract_submitted":False,"demo_ready":False,
  "co_presenter":"NVIDIA_Isaac_team_TBD",
  "key_result_needed":"75%+ SR by Feb 2027",
  "submission_deadline":"2026-11-01"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
