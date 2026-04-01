import datetime,fastapi,uvicorn
PORT=8322
SERVICE="fine_tune_api_v2"
DESCRIPTION="Fine-tuning API v2 — customer-facing training endpoint"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/endpoints')
def e(): return [{'POST':'/fine-tune/start','body':'dataset_path+epochs+gpu_id'},{'GET':'/fine-tune/{job_id}/status'},{'GET':'/fine-tune/{job_id}/checkpoint'},{'POST':'/fine-tune/{job_id}/cancel'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
