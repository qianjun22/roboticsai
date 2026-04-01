import datetime,fastapi,uvicorn
PORT=8622
SERVICE="robot_teleoperation_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/modes")
def modes(): return {"modes":[
  {"name":"kinesthetic_teaching","latency_ms":"<5","use_case":"demo_data"},
  {"name":"spacemouse","latency_ms":"<10","use_case":"fine_grained_manip"},
  {"name":"vr_controller","latency_ms":"<20","use_case":"customer_onsite"},
  {"name":"dagger_expert","latency_ms":"<50","use_case":"online_correction"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
