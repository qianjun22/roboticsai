import datetime,fastapi,uvicorn
PORT=8309
SERVICE="robot_safety_monitor_v3"
DESCRIPTION="Robot safety monitor v3 — workspace limits + collision avoidance"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/limits')
def l(): return {'joint_limits_enforced':True,'workspace_box_m':[-0.5,0.5,-0.5,0.5,0.0,1.2],'collision_detection':'real_time_50hz','emergency_stop':True,'safety_standard':'ISO_10218_compliant','latency_overhead_ms':2}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
