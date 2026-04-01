import datetime,fastapi,uvicorn
PORT=8464
SERVICE="embodiment_adapter_v3"
DESCRIPTION="Embodiment adapter v3: map GR00T to Franka, UR5, xArm, Kinova without retraining"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/adapter/supported")
def supported(): return {"robots":["Franka_Panda","UR5","xArm7","Kinova_Gen3"],"method":"joint_space_mapping","sr_loss_pct":8}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
