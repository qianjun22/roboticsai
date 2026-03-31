import datetime,fastapi,uvicorn
PORT=21041
SERVICE="oci_infra_a100_bare_metal"
DESCRIPTION="OCI bare metal A100: no hypervisor overhead -- GPU at full 312 TFLOPS -- 8% faster than AWS VM"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
