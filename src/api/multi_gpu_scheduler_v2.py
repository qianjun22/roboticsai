import datetime,fastapi,uvicorn
PORT=8301
SERVICE="multi_gpu_scheduler_v2"
DESCRIPTION="Multi-GPU job scheduler v2 — 8xA100 OCI allocation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/schedule')
def s(): return {'gpus':8,'gpu_type':'A100_80GB','allocation':{'gpu0':'inference_server','gpu1':'eval_jobs','gpu2':'sdg_data_gen','gpu3':'dagger_finetune','gpu4-7':'batch_inference'},'utilization':{'gpu0':9,'gpu3':95}}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
