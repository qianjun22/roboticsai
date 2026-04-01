import datetime,fastapi,uvicorn
PORT=8770
SERVICE="robot_cloud_jun_bio"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/bio")
def bio(): return {"name":"Jun Qian","role":"OCI Product Manager",
  "focus":"Robot Cloud — foundation model fine-tuning for robotics on OCI",
  "background":"LLM_infra_PM_pivoting_to_embodied_AI",
  "github":"qianjun22","project":"OCI Robot Cloud",
  "contact_for_pilots":"via_Oracle_OCI"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
