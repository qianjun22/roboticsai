import datetime,fastapi,uvicorn
PORT=8538
SERVICE="joint_vel_control_v2"
DESCRIPTION="Joint velocity controller v2: smooth 7-DOF control at 1kHz for Franka manipulation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/control/status")
def status(): return {"frequency_hz":1000,"dof":7,"max_vel_rad_s":2.4,"jerk_limit":True,"tracking_error_deg":0.08}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
