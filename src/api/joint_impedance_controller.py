import datetime,fastapi,uvicorn
PORT=8462
SERVICE="joint_impedance_controller"
DESCRIPTION="Joint impedance controller: stiffness/damping tuning via RL for compliant manipulation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/controller/params")
def params(): return {"stiffness":[300,300,300,80,80,80,40],"damping":[14,14,14,5.7,5.7,5.7,3.2],"mode":"variable_impedance"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
