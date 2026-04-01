import datetime,fastapi,uvicorn
PORT=8356
SERVICE="team_hire_tracker"
DESCRIPTION="Team hiring tracker — first engineering hire"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/roles')
def r(): return [{'role':'ML_Engineer_DAgger','level':'senior_L5','salary':220000,'equity':0.5,'start_date':'Q3_2026','requirements':['PyTorch','robot_learning','DAgger_or_RL']},{'role':'DevRel_Engineer','level':'mid_L4','salary':180000,'equity':0.3,'start_date':'Q4_2026'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
