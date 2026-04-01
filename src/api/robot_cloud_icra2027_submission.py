import datetime,fastapi,uvicorn
PORT=8753
SERVICE="robot_cloud_icra2027_submission"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/submission")
def submission(): return {"venue":"ICRA_2027","deadline":"2026-09-15",
  "title":"OCI Robot Cloud: Infrastructure for Scalable Robot Foundation Model Fine-Tuning",
  "pages":8,"status":"planned","note":"systems_paper_not_ML"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
