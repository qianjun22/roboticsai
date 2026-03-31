import datetime,fastapi,uvicorn
PORT=15563
SERVICE="groot_n3_oci_infra"
DESCRIPTION="GR00T N3 OCI infra: 8x A100 80GB for inference (vs 1x for N1.6) — enterprise GPU tier required"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
