import datetime,fastapi,uvicorn
PORT=8287
SERVICE="eval_scheduler"
DESCRIPTION="Automated eval scheduler — trigger after each DAgger run"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/schedule')
def schedule(): return {'trigger':'after_final_iter_complete','episodes':20,'metrics':['SR','latency_ms','cube_z_max'],'auto_launch_next_run':True,'sr_threshold_to_continue':0.10}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
