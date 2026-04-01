import datetime,fastapi,uvicorn
PORT=8690
SERVICE="robot_cloud_transfer_learning"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/transfer_config")
def transfer_config(): return {
  "source_task":"cube_lift_Franka","target_tasks":["cube_lift_UR5","cube_lift_xArm"],
  "method":"embodiment_adapter_layers","frozen_layers":"trunk","trainable":"head+adapters",
  "est_demos_for_transfer":50,"vs_from_scratch":300,"timeline":"run16+"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
