import datetime,fastapi,uvicorn
PORT=16061
SERVICE="ft_sensor_spec"
DESCRIPTION="Robotiq FT300-S: 100Hz sampling, ±200N forces, ±30Nm torques, RS485 + USB — Franka-compatible"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
