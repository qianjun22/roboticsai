import datetime,fastapi,uvicorn
PORT=8608
SERVICE="groot_model_registry_v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/models")
def models(): return {"registry":[
  {"id":"groot_n1.6_base","type":"foundation","params":"3B","source":"NVIDIA"},
  {"id":"run8_iter1","type":"dagger","sr_est":"5-15%","episodes":50,"steps":5000},
  {"id":"run9_iter_best","type":"dagger","sr_est":"15-30%","status":"training"},
  {"id":"run10_iter_best","type":"dagger","sr_est":"25-40%","status":"planned"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
