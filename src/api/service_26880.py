import datetime,fastapi,uvicorn
PORT=26880
SERVICE="korea_summary"
DESCRIPTION="Korea: Seoul office Q2 2030, Ji-ho hire, Samsung SDI + Hyundai + LG, $30M ARR, KIST collaboration, chaebol chain"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
