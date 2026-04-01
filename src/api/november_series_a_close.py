import datetime,fastapi,uvicorn
PORT=8474
SERVICE="november_series_a_close"
DESCRIPTION="November 2026: Series A close $8M at $40M valuation, OCI Robot Cloud official product"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/fundraise")
def fundraise(): return {"round":"Series_A","target_usd":8000000,"valuation_usd":40000000,"month":"Nov-2026"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
