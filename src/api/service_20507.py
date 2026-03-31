import datetime,fastapi,uvicorn
PORT=20507
SERVICE="jul26_ops_jul5_offer"
DESCRIPTION="Jul 5 10:52am: Zach: 'we want to lead your Series A -- $6M, are you fundraising?' -- Jun: 'yes'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
