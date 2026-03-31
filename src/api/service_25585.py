import datetime,fastapi,uvicorn
PORT=25585
SERVICE="oci_compute_cost_2028"
DESCRIPTION="OCI H100 cost 2028: $4.10/hr -- H100 is 3x faster than A100 for LoRA -- effective cost $1.37/hr equivalent"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
