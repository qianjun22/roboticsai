import datetime,fastapi,uvicorn
PORT=21184
SERVICE="ir_series_b_metrics"
DESCRIPTION="Series B metrics: 15 customers, $3.6M ARR, 145% NRR, 78% GM, $18M ARR path -- data-driven"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
