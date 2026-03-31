import datetime,fastapi,uvicorn
PORT=26240
SERVICE="ipo_summary"
DESCRIPTION="IPO: March 2028, RCLD NYSE, $10/share, $2B market cap, 3.5x oversubscribed, Goldman lead, first robotics AI IPO"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
