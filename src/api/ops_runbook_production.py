import datetime,fastapi,uvicorn
PORT=8859
SERVICE="ops_runbook_production"
DESCRIPTION="Production ops runbook — incident response for OCI Robot Cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/runbook")
def runbook(): return {"incidents":{"inference_latency_spike":{"threshold_ms":500,"steps":["check GPU utilization","restart groot_franka_server.py","scale to backup GPU"]},"fine_tune_oom":{"cause":"batch_size too large","fix":"reduce to batch_size=8"},"dagger_policy_query_failed":{"cause":"inference server not ready","fix":"wait /act warmup (commit 3c61f52)"}},"on_call":"jun@roboticsai.dev","sla":"99.9pct uptime, <500ms P99 inference","monitoring":"OCI Monitoring + Grafana"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
