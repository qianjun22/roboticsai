import datetime,fastapi,uvicorn
PORT=8521
SERVICE="teleoperation_data_collector_v3"
DESCRIPTION="Teleoperation data collector v3: VR glove + SpaceMouse, 50 demos/day, quality filters"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/collector/stats")
def stats(): return {"method":"SpaceMouse+VR_glove","demos_per_day":50,"quality_filter_pct":87,"avg_demo_sec":22,"operator_sr":0.94}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
