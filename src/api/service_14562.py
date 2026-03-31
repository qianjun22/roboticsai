import datetime,fastapi,uvicorn
PORT=14562
SERVICE="org_design_series_a"
DESCRIPTION="Series A org: CEO, CTO (hire), Head of Sales, 4 ML eng, 2 robotics eng, 2 AEs, 1 CSM — 12 people"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
