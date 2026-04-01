import datetime,fastapi,uvicorn
PORT=8878
SERVICE="run12_ft_sensor_cube_place"
DESCRIPTION="DAgger run12 with F/T sensor — cube_place task enabled by contact feedback"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"run":12,"new_sensor":"ATI Mini45 F/T (6-axis, 7kHz)","new_task":"cube_place (lift + place on marked target)","obs_addition":"[Fx,Fy,Fz,Tx,Ty,Tz] normalized to [-1,1]","success_criteria":{"cube_place":"cube center within 5cm of target, z<0.1m"},"genesis_change":"F/T sensor sim model + contact detection","expected_sr":"cube_pick 100pct + cube_place 60pct","combined_task_sr_target":"70pct (sequential)","timeline":"Q3 2026 after real robot delivery"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
