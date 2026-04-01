import datetime,fastapi,uvicorn
PORT=8317
SERVICE="observability_stack"
DESCRIPTION="Observability stack — metrics, logs, traces"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/stack')
def s(): return {'metrics':'Prometheus+Grafana','logs':'OCI_Logging_Service','traces':'Jaeger','alerting':'PagerDuty','dashboards':['GPU_utilization','latency_percentiles','training_loss','SR_over_time','cost_per_inference']}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
