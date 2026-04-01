import datetime,fastapi,uvicorn
PORT=8780
SERVICE="robot_cloud_cost_comparator"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/compare")
def compare(): return {"fine_tune_run_1000_steps":{
    "OCI_A100":0.0043,"AWS_p4d":0.041,"GCP_A100":0.038,"ratio_vs_aws":9.6},
  "notes":"OCI BM.GPU.A100 vs AWS p4d.24xlarge"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
