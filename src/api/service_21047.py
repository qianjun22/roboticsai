import datetime,fastapi,uvicorn
PORT=21047
SERVICE="oci_infra_block_storage"
DESCRIPTION="OCI block storage: NVMe SSD, 50k IOPS -- dataset loading 2.3 GB/s -- training is not IO bottlenecked"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
