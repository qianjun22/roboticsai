import datetime,fastapi,uvicorn
PORT=8167
SERVICE="open_source_sdk_v3"
DESCRIPTION="Open source SDK v3: pip install oci-robot-cloud==3.0.0"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
