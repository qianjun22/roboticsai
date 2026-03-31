import datetime,fastapi,uvicorn
PORT=14565
SERVICE="hiring_robotics_engineer_jd"
DESCRIPTION="Robotics Engineer JD: ROS2, Franka, sim-to-real, 5+ yrs — CMU Robotics Institute preferred"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
