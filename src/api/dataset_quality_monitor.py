import datetime,fastapi,uvicorn
PORT=8289
SERVICE="dataset_quality_monitor"
DESCRIPTION="Dataset quality monitor — episode length distribution"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/quality')
def quality(): return {'min_frames_threshold':10,'run8_iter1_episodes':50,'run8_iter2_episodes':49,'run8_short_episode_rate':'unknown','issue':'beta_decay_collapse_means_GR00T_server_barely_queried'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
