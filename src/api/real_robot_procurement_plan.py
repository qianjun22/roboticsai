import datetime,fastapi,uvicorn
PORT=8845
SERVICE="real_robot_procurement_plan"
DESCRIPTION="Real robot procurement plan — Franka Panda for sim-to-real validation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/plan")
def plan(): return {"robot":"Franka Research 3 (FR3)","cost":"~$35k USD","delivery_lead_time":"8-12 weeks","accessories":["ATI Mini45 F/T sensor ($8k)","Intel RealSense D435 wrist cam ($200)","OAK-D overhead cam ($300)","workbench + safety cage"],"total_budget":"~$45k","procurement_route":"Oracle research equipment request via Greg Pavlik","alternative":"partner site eval at NVIDIA-referred startup","timeline":"order by June 2026 for Q3 delivery"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
