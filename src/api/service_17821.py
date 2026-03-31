import datetime,fastapi,uvicorn
PORT=17821
SERVICE="post_ipo_war_chest"
DESCRIPTION="Post-IPO: $200M raised — deployment plan: 50% eng, 20% sales, 20% intl, 10% R&D — 24-month plan"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
