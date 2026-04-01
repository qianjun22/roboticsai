import datetime,fastapi,uvicorn
PORT=8839
SERVICE="force_torque_sensor_plan"
DESCRIPTION="Force-torque sensor integration plan for run12 — contact-rich manipulation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/spec")
def spec(): return {"sensor":"ATI Mini45 F/T","axes":6,"force_range_N":145,"torque_range_Nm":5,"sample_rate_hz":7000,"mount":"Franka flange between robot and gripper","use_case":"contact detection for cube grasping","genesis_integration":"F/T obs added to policy input","planned_run":"run12","expected_gain":"robust grasp on novel objects","cube_place_task":"enabled by F/T feedback"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
