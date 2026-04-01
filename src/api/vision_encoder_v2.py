import datetime,fastapi,uvicorn
PORT=8369
SERVICE="vision_encoder_v2"
DESCRIPTION="Vision encoder v2 — camera processing for robot policies"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/spec')
def s(): return {'encoder':'DinoV2_large','input_resolution':[480,640],'cameras':['wrist','overhead'],'feature_dim':1024,'fine_tuned_with_policy':True,'vs_frozen_encoder_sr_improvement':'TBD'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
