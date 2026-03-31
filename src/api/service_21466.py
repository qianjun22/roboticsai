import datetime,fastapi,uvicorn
PORT=21466
SERVICE="ft_sensor_cost_analysis"
DESCRIPTION="F/T ROI: $1,200 sensor + 1hr + 1 day demos = $1,600 for 5pp SR = $320 per SR point"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
