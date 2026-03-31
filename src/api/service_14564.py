import datetime,fastapi,uvicorn
PORT=14564
SERVICE="hiring_ml_engineer_jd"
DESCRIPTION="ML Engineer JD: GR00T fine-tuning, DAgger, PyTorch, OCI, 3+ yrs — Stanford/CMU/Berkeley pref"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
