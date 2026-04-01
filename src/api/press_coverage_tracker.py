import datetime,fastapi,uvicorn
PORT=8274
SERVICE="press_coverage_tracker"
DESCRIPTION="Press and media coverage tracker for OCI Robot Cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/coverage')
def coverage(): return {'targets':['TechCrunch','VentureBeat','IEEE_Spectrum','The_Robot_Report'],'status':'pre-launch','expected_date':'2026-10','story_angle':'Oracle_enters_embodied_AI_market'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
