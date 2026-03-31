import datetime,fastapi,uvicorn
PORT=15777
SERVICE="groot_action_decoder"
DESCRIPTION="Action decoder: 20-step trajectory MLP — outputs (x,y,z,rx,ry,rz,gripper) × 20 steps = 140-dim"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
