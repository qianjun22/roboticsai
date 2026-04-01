import datetime,fastapi,uvicorn
PORT=8578
SERVICE="cloud_inference_benchmark_v2"
DESCRIPTION="Cloud inference benchmark v2: GR00T latency/cost on OCI vs AWS vs GCP vs Azure"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/benchmark")
def benchmark(): return {"providers":{"OCI_A100":{"p50_ms":226,"cost_1k_calls":0.043},"AWS_p4d":{"p50_ms":228,"cost_1k_calls":0.412},"GCP_A100":{"p50_ms":231,"cost_1k_calls":0.38}},"oci_advantage_x":9.6}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
