import datetime,fastapi,uvicorn
PORT=15161
SERVICE="oci_a100_cluster"
DESCRIPTION="OCI A100 cluster: 8x A100 80GB per node, NVLink 600GB/s, 100GbE RDMA — robotics-grade infra"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
