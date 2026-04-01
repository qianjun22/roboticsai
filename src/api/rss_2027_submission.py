import datetime,fastapi,uvicorn
PORT=8537
SERVICE="rss_2027_submission"
DESCRIPTION="RSS 2027 paper: multi-task DAgger, 65%+ SR, cloud robotics platform evaluation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/paper")
def paper(): return {"title":"Cloud-Native Robot Learning: From 5% to 65%+ SR with Online DAgger on OCI","venue":"RSS 2027","deadline":"2027-01-15","status":"planning"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
