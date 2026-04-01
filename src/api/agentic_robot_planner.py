import datetime,fastapi,uvicorn
PORT=8425
SERVICE="agentic_robot_planner"
DESCRIPTION="Agentic robot planner — autonomous multi-step task execution"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/capabilities')
def c(): return {'task_horizon_steps':10,'replanning':True,'failure_recovery':True,'goal_tracking':True,'current_sr_multi_step':0.02,'single_step_sr':0.05,'architecture':'GR00T_with_LLM_retry_loop'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
