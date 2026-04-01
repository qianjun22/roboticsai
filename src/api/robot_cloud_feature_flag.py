import datetime,fastapi,uvicorn
PORT=8686
SERVICE="robot_cloud_feature_flag"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/flags")
def flags(): return {"flags":[
  {"flag":"wrist_camera","enabled":False,"rollout":"run10"},
  {"flag":"force_torque_obs","enabled":False,"rollout":"run12"},
  {"flag":"language_cond","enabled":False,"rollout":"run14"},
  {"flag":"multi_task","enabled":False,"rollout":"run16"},
  {"flag":"rl_polish","enabled":False,"rollout":"run15"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
