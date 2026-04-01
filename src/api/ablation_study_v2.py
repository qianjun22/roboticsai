import datetime,fastapi,uvicorn
PORT=8334
SERVICE="ablation_study_v2"
DESCRIPTION="Ablation study tracker v2 — SDG components"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/ablations')
def a(): return [{'component':'IK_motion_planning','without_mae':0.090,'with_mae':0.013,'improvement':'6.9x'},{'component':'domain_randomization','without_mae':0.045,'with_mae':0.013,'improvement':'3.5x'},{'component':'multi_camera','without_mae':0.031,'with_mae':0.013,'improvement':'2.4x'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
