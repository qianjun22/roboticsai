import datetime,fastapi,uvicorn
PORT=16065
SERVICE="ft_policy_input"
DESCRIPTION="F/T policy input: 6-DOF wrench (Fx,Fy,Fz,Tx,Ty,Tz) appended to observation — 26-dim total"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
