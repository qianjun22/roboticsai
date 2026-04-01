import datetime,fastapi,uvicorn
PORT=8298
SERVICE="competitive_analysis_v2"
DESCRIPTION="Competitive analysis v2 — OCI vs AWS vs Azure for robot training"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/comparison')
def c(): return [{'cloud':'OCI','gpu':'A100_80GB','cost_per_step':0.0043,'latency_ms':226,'nvidia_stack':True,'us_origin':True,'score':95},{'cloud':'AWS_p4d','gpu':'A100_40GB','cost_per_step':0.0413,'latency_ms':389,'nvidia_stack':False,'score':45},{'cloud':'Azure_NDv4','gpu':'A100_80GB','cost_per_step':0.0387,'latency_ms':412,'nvidia_stack':False,'score':48}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
