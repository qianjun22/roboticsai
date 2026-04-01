import datetime,fastapi,uvicorn
PORT=8380
SERVICE="oci_logging_service"
DESCRIPTION="OCI Logging Service integration — centralized logs"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def c(): return {'log_groups':['training','inference','eval','system'],'retention_days':90,'search':'OCI_Log_Analytics','structured_logging':True,'correlation_id_tracking':True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
