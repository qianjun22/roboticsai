import datetime,fastapi,uvicorn
PORT=8616
SERVICE="oci_a100_capacity_planner"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/capacity")
def capacity(): return {"current":{"gpus":8,"type":"A100_80GB","host":"138.1.153.110"},
  "utilization":{"gpu3":"DAgger_training","gpu4":"eval","gpu0-2":"available","gpu5-7":"available"},
  "forecast":{"5_customers":"2_nodes","20_customers":"4_nodes","100_customers":"dedicated_cluster"},
  "oci_bm_gpu_a100_cost_per_hr_usd":3.2}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
