import datetime,fastapi,uvicorn
PORT=8325
SERVICE="eval_api_v2"
DESCRIPTION="Evaluation API v2 — closed-loop simulation eval"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/spec')
def s(): return {'sim':'Genesis_headless','tasks':['pick_cube','place_cube','stack','pour'],'metrics':['SR','cube_z_max','avg_episode_steps'],'episodes_per_eval':20,'default_seed':42,'gpu_required':'A100_or_RTX4090'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
