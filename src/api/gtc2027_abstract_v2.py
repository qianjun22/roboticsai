import datetime,fastapi,uvicorn
PORT=8267
SERVICE="gtc2027_abstract_v2"
DESCRIPTION="GTC 2027 talk abstract v2 — refined with run8+ results"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/abstract')
def abstract(): return {'title':'OCI Robot Cloud: Production DAgger on GR00T N1.6','authors':['Jun Qian'],'track':'Robotics_and_Embodied_AI','target_sr_at_submission':'65%+','submission_deadline':'2026-10-15','co_presenter':'NVIDIA_Isaac_team'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
