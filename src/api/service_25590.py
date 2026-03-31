import datetime,fastapi,uvicorn
PORT=25590
SERVICE="oci_cost_per_run_2034"
DESCRIPTION="Cost per fine-tune run 2034: N5 LoRA rank-256 on H200 = $12.40/run -- higher but enterprise justified"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
