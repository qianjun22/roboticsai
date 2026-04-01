import datetime,fastapi,uvicorn
PORT=8754
SERVICE="robot_cloud_neurips2026_submission"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/submission")
def submission(): return {"venue":"NeurIPS_2026_workshop","deadline":"2026-09-01",
  "workshop":"Robot_Learning_Workshop",
  "title":"Cost-Effective DAgger Fine-Tuning of GR00T on OCI A100",
  "status":"planned"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
