import datetime,fastapi,uvicorn
PORT=8866
SERVICE="real_data_collection_teleoperation"
DESCRIPTION="Real data collection via teleoperation — 100 Franka demos for sim-to-real"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/plan")
def plan(): return {"target_demos":100,"interface":"SpaceMouse + keyboard","observations":["overhead RGB","wrist RGB-D","joint positions","gripper state","F/T readings"],"tasks":["pick_cube (50 demos)","place_cube (30 demos)","stack (20 demos)"],"format":"LeRobot HDF5 (same as sim)","use":"domain adaptation fine-tune (run17)","collection_rate":"~10 demos/hour","timeline":"Q3 2026 (after real robot delivery)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
