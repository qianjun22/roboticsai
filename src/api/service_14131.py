import datetime,fastapi,uvicorn
PORT=14131
SERVICE="jan_2027_post_series_a"
DESCRIPTION="Jan 2027 post-Series A: hiring sprint — 3 ML engineers, 2 AEs, 1 CSM — team growing to 12"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
