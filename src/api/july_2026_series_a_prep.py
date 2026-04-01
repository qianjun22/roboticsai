import datetime,fastapi,uvicorn
PORT=8842
SERVICE="july_2026_series_a_prep"
DESCRIPTION="Series A preparation — July 2026 investor outreach with proven results"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/prep")
def prep(): return {"round":"Series A","target_raise":"$8-12M","target_date":"Q1 2027 (post AI World momentum)","july_prep_tasks":["Finalize design partner contracts","Revenue model validation ($5k-$50k/month range)","OCI internal champion: Greg Pavlik","NVIDIA partnership term sheet","3+ customer LOIs"],"deck_status":"CEO pitch v1 ready","lead_investors_target":["NVIDIA Ventures","OCI strategic","Robotics-focused VC"],"ARR_target_at_raise":"$500k ARR (3+ customers)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
