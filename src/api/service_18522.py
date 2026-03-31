import datetime,fastapi,uvicorn
PORT=18522
SERVICE="data_collection_format"
DESCRIPTION="Data format: LeRobot parquet — (timestamp, joint_pos×7, joint_vel×7, img_top×224×224, img_wrist×224×224, task_lang)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
