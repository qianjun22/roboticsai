import datetime,fastapi,uvicorn
PORT=8590
SERVICE="robot_cloud_hiring_plan"
DESCRIPTION="Post-Series A hiring plan: 5 engineers + 2 GTM, robotics ML + cloud infra focus"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/hiring")
def hiring(): return {"headcount_target":8,"roles":["robotics_ML_x2","cloud_infra_x2","robot_control","devrel","enterprise_AE","CSM"],"timeline":"Q1-2027","burn_rate_monthly":180000}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
