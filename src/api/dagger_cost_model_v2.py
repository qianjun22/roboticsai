import datetime,fastapi,uvicorn
PORT=8558
SERVICE="dagger_cost_model_v2"
DESCRIPTION="DAgger cost model v2: per-step, per-iter, per-run pricing on OCI A100 vs AWS p4d"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/cost")
def cost(): return {"oci_a100_per_hr":2.40,"aws_p4d_per_hr":23.10,"oci_per_1k_steps":0.0043,"aws_per_1k_steps":0.0412,"savings_x":9.6,"typical_run_usd":0.43}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
