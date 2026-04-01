import datetime,fastapi,uvicorn
PORT=8422
SERVICE="llm_robot_planning"
DESCRIPTION="LLM robot planning — task decomposition layer"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/arch')
def a(): return {'planner':'GPT4_or_Claude3','executor':'GR00T_N1.6_finetuned','interface':'text_task_to_primitive_subtasks','examples':['pick_up_red_cube→reach+grasp+lift','pour_liquid→reach+grasp+tilt+pour'],'latency_planning_ms':500,'latency_execution_ms':226}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
