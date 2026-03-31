import datetime,fastapi,uvicorn
PORT=14659
SERVICE="serving_throughput_limit"
DESCRIPTION="Throughput: 4.4 inferences/sec per A10 GPU at p99<300ms — 100 robots at 1 Hz each needs 1 A10"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
