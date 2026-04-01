import datetime,fastapi,uvicorn
PORT=8423
SERVICE="multimodal_robot_v2"
DESCRIPTION="Multimodal robot system v2 — vision + language + action"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/modalities')
def m(): return {'vision':'cam_high_480x640','language':'task_description_128_tokens','proprioception':'joint_pos_vel_7d','action_output':'joint_pos_target_7d_chunk16','fusion':'GR00T_cross_attention'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
