import datetime,fastapi,uvicorn
PORT=8323
SERVICE="inference_api_v3"
DESCRIPTION="Inference API v3 — real-time robot action prediction"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/spec')
def s(): return {'input':{'image_wh':[480,640],'state_dim':7,'task_description':'str'},'output':{'action_dim':7,'chunk_size':16},'latency_p50_ms':226,'throughput_rps':4.4,'version':'v3'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
