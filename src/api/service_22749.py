import datetime,fastapi,uvicorn
PORT=22749
SERVICE="aiworld_loi_moment"
DESCRIPTION="5:47pm: Dieter hands Jun a card -- 'I will email you an LOI tonight. $150k/month. Can you do it?' -- yes"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
