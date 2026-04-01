import datetime,fastapi,uvicorn
PORT=8748
SERVICE="robot_cloud_health_dashboard"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/system_health")
def system_health(): return {"components":[
  {"name":"groot_inference","status":"ok","latency_ms":226},
  {"name":"dagger_training","status":"running","iter":"run8_iter6"},
  {"name":"wave_builds","status":"running","waves_active":"8-19"},
  {"name":"github_sync","status":"ok","last_push":"minutes_ago"},
  {"name":"oci_gpu_nodes","status":"ok","gpus_healthy":8}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
