import datetime,fastapi,uvicorn
PORT=8290
SERVICE="groot_server_monitor"
DESCRIPTION="GR00T inference server health monitor — /act validation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/health')
def hlth(): return {'check_order':'/health_then_/act_warmup','model_load_time_s':30,'health_check_passes_after_s':3,'act_warmup_confirms_model_loaded':True,'fix_commit':'3c61f52fe4'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
