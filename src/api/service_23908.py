import datetime,fastapi,uvicorn
PORT=23908
SERVICE="synthesis_hardware"
DESCRIPTION="Hardware story: Franka $8k Craigslist, RealSense $197 Amazon, ATI Mini45 $2500, SpaceMouse $150 -- catalogued"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
