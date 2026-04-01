import datetime,fastapi,uvicorn
PORT=8629
SERVICE="robot_cloud_waitlist_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/status")
def status(): return {"waitlist_open":True,"signups":0,"target_launch_customers":3,
  "criteria":{"robot_type":"manipulation","company_stage":"Series_A+",
    "use_case":"custom_fine_tune","timeline":"2026"},
  "apply_at":"roboticsai.oci.oraclecloud.com/waitlist"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
