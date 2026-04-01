import datetime,fastapi,uvicorn
PORT=8532
SERVICE="robot_cloud_press_kit"
DESCRIPTION="Press kit: OCI Robot Cloud launch, key metrics, exec quotes, product screenshots"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/press/kit")
def press_kit(): return {"headline":"OCI Robot Cloud: 9.6x cheaper than AWS, full NVIDIA stack","key_metrics":{"sr_improvement":"8.4x","cost_vs_aws":"9.6x_cheaper","latency_ms":226},"launch_date":"2026-09-18"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
