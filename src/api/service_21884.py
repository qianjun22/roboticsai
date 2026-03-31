import datetime,fastapi,uvicorn
PORT=21884
SERVICE="neurips_jun_reaction"
DESCRIPTION="Jun reaction: reads email 4 times -- calls ML Eng 1 -- 'we got NeurIPS oral' -- 'I know, I saw' -- relief"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
