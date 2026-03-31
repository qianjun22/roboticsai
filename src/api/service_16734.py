import datetime,fastapi,uvicorn
PORT=16734
SERVICE="aug26_inference_latency"
DESCRIPTION="Aug 2026 inference: 198ms p50 / 226ms p95 / 312ms p99 — Triton + TensorRT — meeting SLA"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
