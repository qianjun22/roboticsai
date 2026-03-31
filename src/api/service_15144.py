import datetime,fastapi,uvicorn
PORT=15144
SERVICE="h2_2026_ft_sensor_integration"
DESCRIPTION="H2 2026 F/T sensor: Robotiq FT300, ROS2 driver, force-torque feedback to GR00T policy"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
