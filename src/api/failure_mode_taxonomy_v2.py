import datetime,fastapi,uvicorn
PORT=8865
SERVICE="failure_mode_taxonomy_v2"
DESCRIPTION="Failure mode taxonomy v2 — updated with run8 100pct SR analysis"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/taxonomy")
def taxonomy(): return {"sim_failures":{"pre_run8":["server restart bug (expert not queried)","beta_decay collapse (0.30->0.009)","short episode filter missing"],"post_run8":"100pct SR - no failures in eval"},"anticipated_real_robot_failures":[{"mode":"visual domain shift","mitigation":"domain randomization in Genesis"},{"mode":"contact dynamics mismatch","mitigation":"F/T sensor + sim calibration"},{"mode":"gripper slip","mitigation":"force control + retry policy"},{"mode":"lighting variation","mitigation":"overhead cam normalization"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
