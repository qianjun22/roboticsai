import datetime,fastapi,uvicorn
PORT=26347
SERVICE="series_c_use_of_proceeds"
DESCRIPTION="Use of proceeds: $120M Bangalore R&D center, $80M OCI reserved GPU, $60M sales APAC, $40M acquisitions"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
