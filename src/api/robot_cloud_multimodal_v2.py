import datetime,fastapi,uvicorn
PORT=8682
SERVICE="robot_cloud_multimodal_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/modalities")
def modalities(): return {"current":["rgb","robot_state"],
  "planned_run10":["wrist_rgb","wrist_depth"],
  "planned_run12":["force_torque","tactile"],
  "planned_run14":["language_instruction"],
  "planned_run16":["audio","point_cloud"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
