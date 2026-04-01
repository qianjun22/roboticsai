import datetime,fastapi,uvicorn
PORT=8396
SERVICE="eval_protocol_v2"
DESCRIPTION="Evaluation protocol v2 — standardized after run7 lessons"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/protocol')
def p(): return {'episodes':20,'seed':42,'max_steps_per_ep':150,'success_threshold_m':0.78,'cube_z_metric':True,'latency_metric':True,'report_format':'json+csv','required_before':'any_DAgger_run_launch'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
