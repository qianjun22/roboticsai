import datetime,fastapi,uvicorn
PORT=8415
SERVICE="eval_environment_v3"
DESCRIPTION="Evaluation environment v3 — standardized conditions"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def c(): return {'seed':42,'cube_pos_fixed':True,'lighting_standard':True,'camera_angles':'nominal','no_domain_rand':True,'metric':'cube_z_gt_0.78m','episodes':20,'headless':True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
