import datetime,fastapi,uvicorn
PORT=8419
SERVICE="reward_shaping_v2"
DESCRIPTION="Reward shaping v2 — dense + sparse for RL fine-tuning"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/rewards')
def r(): return {'sparse':{'success':10.0,'fail':-1.0},'dense':{'cube_z_delta':0.1,'dist_to_cube':-0.01,'grasp_force_ok':0.5},'current_use':'BC_only_no_RL_yet','planned':'run12_RL_finetune'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
