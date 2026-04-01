import datetime,fastapi,uvicorn
PORT=8285
SERVICE="training_pipeline_monitor"
DESCRIPTION="Real-time training pipeline monitor — DAgger + fine-tune status"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/status')
def status(): return {'active_run':'run8','iteration':'3/6','beta_current':0.0,'server_status':'warned_not_ready','fine_tune_step':'pending','next_action':'iter3_data_collection'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
