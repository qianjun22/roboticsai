import datetime,fastapi,uvicorn
PORT=8626
SERVICE="robot_cloud_blog_planner_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/posts")
def posts(): return {"planned_posts":[
  {"title":"How We Got 5% Closed-Loop SR on OCI A100 (Baseline)","publish":"2026-04","status":"draft"},
  {"title":"DAgger on GR00T: What We Learned from Run 8","publish":"2026-05","status":"planned"},
  {"title":"From 5% to 30%: DAgger Run 9 Results","publish":"2026-06","status":"planned"},
  {"title":"OCI Robot Cloud: AI World Demo Recap","publish":"2026-09","status":"planned"},
  {"title":"GTC 2027: 75%+ SR and What Comes Next","publish":"2027-03","status":"planned"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
