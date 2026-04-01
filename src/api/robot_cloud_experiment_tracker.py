import datetime,fastapi,uvicorn
PORT=8768
SERVICE="robot_cloud_experiment_tracker"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/experiments")
def experiments(): return {"tracking_tool":"Weights_and_Biases",
  "logged_metrics":["loss","sr","inference_latency","episode_length","beta"],
  "experiments":[{"id":"run8","status":"running","iters_complete":5},{"id":"run9","status":"planned"}],
  "project":"oci-robot-cloud","entity":"qianjun22"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
