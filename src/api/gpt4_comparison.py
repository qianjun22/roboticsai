import datetime,fastapi,uvicorn
PORT=8421
SERVICE="gpt4_comparison"
DESCRIPTION="GPT-4 vs GR00T comparison — language model for robotics"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/comparison')
def c(): return {'gpt4_v_groot':{'gpt4':'text_only_cannot_control_robot_directly','groot':'multimodal_can_output_robot_actions'},'recommended':'GR00T_for_robot_control_GPT4_for_planning','integration':'GPT4_plans_GR00T_executes'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
