import datetime,fastapi,uvicorn
PORT=8411
SERVICE="genesis_sim_v3"
DESCRIPTION="Genesis simulation v3 — RTX + IK + domain randomization"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def c(): return {'engine':'Genesis_0.2.1','renderer':'RTX_pathtracing','physics':'PhysX_5','robot':'Franka_Panda','domain_rand':True,'episodes_per_hour':200,'gpu_required':'A100_or_RTX4090'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
