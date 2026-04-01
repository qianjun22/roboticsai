import datetime,fastapi,fastapi.responses,uvicorn
PORT=9454
SERVICE="kinesthetic_teach_v2"
DESCRIPTION="Kinesthetic teaching v2 guided demos"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/kinesthetic-teach-v2")
def domain(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT,"status":"active"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
