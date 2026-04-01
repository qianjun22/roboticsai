import datetime,fastapi,uvicorn
PORT=8416
SERVICE="trajectory_recorder"
DESCRIPTION="Trajectory recorder — action + observation logging"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/spec')
def s(): return {'format':'HDF5_LeRobot_v2','observations':['cam_high_480x640','joint_pos_7d','joint_vel_7d'],'actions':['joint_pos_target_7d'],'fps':30,'compression':'gzip','episode_size_mb':15}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
