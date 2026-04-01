import datetime,fastapi,uvicorn
PORT=8364
SERVICE="reward_model_v2"
DESCRIPTION="Reward model v2 — learned reward from human feedback"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/model')
def m(): return {'type':'preference_learning','input':'video_pairs_of_attempts','output':'scalar_reward','training_samples_needed':500,'use_case':'replace_cube_z_threshold_with_learned_reward','status':'planned_q3_2026'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
