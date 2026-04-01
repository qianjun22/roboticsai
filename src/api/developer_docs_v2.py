import datetime,fastapi,uvicorn
PORT=8383
SERVICE="developer_docs_v2"
DESCRIPTION="Developer documentation v2 — quickstart + API reference"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/sections')
def s(): return ['quickstart_5min','fine_tune_your_robot_tutorial','dagger_training_guide','inference_api_reference','python_sdk_reference','deployment_guide','troubleshooting','examples_gallery']
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
