import datetime,fastapi,uvicorn
PORT=21291
SERVICE="groot_day1_200pm"
DESCRIPTION="2:00pm: Jun reads DAgger paper -- 'Dataset Aggregation' -- 'this is how we go from 5% to 30%' -- reads twice"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
