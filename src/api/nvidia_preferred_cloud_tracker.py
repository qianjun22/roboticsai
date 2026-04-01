import datetime,fastapi,uvicorn
PORT=8561
SERVICE="nvidia_preferred_cloud_tracker"
DESCRIPTION="NVIDIA preferred cloud program: OCI as recommended cloud for Isaac + GR00T customers"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/program")
def program(): return {"status":"targeting","current_stage":"LOI_pending","sponsor":"NVIDIA_robotics_BDM","benefit":"OCI_in_NVIDIA_Isaac_docs","referral_potential":"50_startups_yr"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
