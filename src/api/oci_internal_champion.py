import datetime,fastapi,uvicorn
PORT=8346
SERVICE="oci_internal_champion"
DESCRIPTION="OCI internal champion strategy"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/champions')
def c(): return [{'name':'Greg_Pavlik','role':'Oracle_CTO','ask':'NVIDIA_intro','status':'pitch_pending'},{'name':'Clay_Magouyrk','role':'OCI_EVP','ask':'product_license','status':'pitch_pending'},{'name':'Startup_team','role':'OCI_Startup_Program','ask':'design_partner_refs','status':'outreach_started'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
