import datetime,fastapi,uvicorn
PORT=8528
SERVICE="robot_simulation_accuracy_v3"
DESCRIPTION="Sim accuracy v3: Genesis vs IsaacSim vs MuJoCo on cube lift task physical accuracy"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/accuracy")
def accuracy(): return {"simulators":{"Genesis":{"fps":430000,"contact_acc":0.87,"sim_to_real_gap":23.6},"IsaacSim":{"fps":50000,"contact_acc":0.91,"sim_to_real_gap":18.2},"MuJoCo":{"fps":180000,"contact_acc":0.89,"sim_to_real_gap":21.4}}}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
