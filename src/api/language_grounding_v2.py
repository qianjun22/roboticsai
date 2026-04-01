import datetime,fastapi,uvicorn
PORT=8367
SERVICE="language_grounding_v2"
DESCRIPTION="Language grounding v2 — natural language task conditioning"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/capabilities')
def c(): return {'model':'GR00T_N1.6_VLA','input_modalities':['image','language','joint_state'],'task_prompts':['pick up the red cube','place it on the blue plate','stack the blocks'],'zero_shot_sr':0.02,'fine_tuned_sr':0.05,'status':'current_baseline'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
