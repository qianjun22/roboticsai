import datetime,fastapi,uvicorn
PORT=8779
SERVICE="robot_cloud_force_control"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"mode":"impedance_control","stiffness_Nm_rad":200,
  "use_with_DAgger":"force_torque_as_obs_run12+"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
