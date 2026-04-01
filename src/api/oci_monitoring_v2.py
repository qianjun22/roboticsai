import datetime,fastapi,uvicorn
PORT=8379
SERVICE="oci_monitoring_v2"
DESCRIPTION="OCI Monitoring v2 — custom metrics and alarms"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/alarms')
def a(): return [{'name':'gpu_utilization_low','threshold_pct':20,'window_min':10,'action':'slack_notify'},{'name':'training_stuck','metric':'loss_plateau_steps','threshold':500,'action':'page_oncall'},{'name':'sr_regression','threshold':0.02,'action':'halt_deployment'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
