import datetime,fastapi,uvicorn
PORT=8834
SERVICE="wrist_camera_integration_v1"
DESCRIPTION="Wrist camera integration for run10 — visual feedback for grasping"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/spec")
def spec(): return {"camera":"Intel RealSense D435","resolution":"640x480","fps":30,"mount":"Franka EE flange","use_case":"close-range grasp verification","genesis_sim":"wrist cam obs added to observation space","planned_run":"run10","expected_gain":"improved grasp contact detection","estimated_sr_delta":"+10-15pct over run9"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
