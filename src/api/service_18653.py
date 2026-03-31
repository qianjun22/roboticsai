import datetime,fastapi,uvicorn
PORT=18653
SERVICE="roadshow_employee_value"
DESCRIPTION="Employee value: ML eng 1 (0.5%, pre-dilution) → $10M+ — SRE 1 (0.3%) → $6M+ — life-changing"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
