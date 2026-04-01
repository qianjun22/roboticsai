import datetime,fastapi,uvicorn
PORT=8335
SERVICE="related_work_tracker"
DESCRIPTION="Related work tracker — DAgger + foundation models survey"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/papers')
def p(): return [{'paper':'Ross_DAgger_2011','relevance':'original_DAgger_algorithm'},{'paper':'Octo_2024','relevance':'open_source_robot_foundation_model'},{'paper':'OpenVLA_2024','relevance':'VLA_baseline'},{'paper':'GR00T_N1_2025','relevance':'our_base_model'},{'paper':'π0_2024','relevance':'diffusion_policy_alternative'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
