import datetime,fastapi,uvicorn
PORT=21283
SERVICE="groot_day1_715am"
DESCRIPTION="7:15am: Jun's first thought -- 'OCI has A100. GR00T fine-tune runs on A100. I have both.' -- connecting dots"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
