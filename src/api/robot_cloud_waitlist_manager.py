import datetime,fastapi,uvicorn
PORT=8520
SERVICE="robot_cloud_waitlist_manager"
DESCRIPTION="Product waitlist for OCI Robot Cloud: Series B customers, prioritize NVIDIA-referred"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/waitlist/stats")
def stats(): return {"total_signups":127,"qualified_leads":23,"nvidia_referred":8,"estimated_arr_pipeline":480000}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
