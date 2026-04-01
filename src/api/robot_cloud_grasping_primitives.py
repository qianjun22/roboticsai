import datetime,fastapi,uvicorn
PORT=8778
SERVICE="robot_cloud_grasping_primitives"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/primitives")
def primitives(): return {"approach":"GR00T_end_to_end","no_explicit_primitives":True,
  "current_sr":"100%_run8","grasp_types_learned":["power","precision","pinch"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
