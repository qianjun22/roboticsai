import datetime,fastapi,uvicorn
PORT=8324
SERVICE="dataset_api_v2"
DESCRIPTION="Dataset management API v2 — upload, version, validate"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/endpoints')
def e(): return [{'POST':'/dataset/upload','formats':['LeRobot_HDF5','RLDS']},{'GET':'/dataset/{id}/stats'},{'POST':'/dataset/{id}/validate'},{'GET':'/dataset/list'},{'DELETE':'/dataset/{id}'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
