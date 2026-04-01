import datetime,fastapi,uvicorn
PORT=8519
SERVICE="multi_task_curriculum_v3"
DESCRIPTION="Multi-task curriculum v3: lift -> stack -> insert -> pour, 4 tasks in one GR00T model"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/curriculum")
def curriculum(): return {"tasks":["lift","stack","insert","pour"],"sr":[0.42,0.18,0.09,0.0],"multi_task_model_sr_avg":0.17,"single_task_avg":0.42,"transfer_gain":0.0}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
